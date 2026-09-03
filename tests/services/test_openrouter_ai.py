import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from app.models.domain import (
    AIOutcome,
    Document,
    DocumentMediaType,
    Report,
    ReportDocument,
    ReportDocumentRole,
    ReportStatus,
    ReportType,
)
from app.services.openrouter_ai import (
    OpenRouterCriterionExtractor,
    OpenRouterReportAnalyzer,
    OpenRouterUnavailableError,
)
from app.services.ports import (
    AIInputDocument,
    CriterionExtractionRequest,
    ReportAnalysisRequest,
)
from app.services.storage import InMemoryDocumentStorage


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _make_pdf(text: str) -> bytes:
    import pymupdf

    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), text)
        return pdf.tobytes()


def _make_document(**overrides) -> Document:
    defaults = dict(
        id=uuid4(),
        project_id=uuid4(),
        display_name="Synthetic document",
        original_filename="synthetic.pdf",
        media_type=DocumentMediaType.PDF,
        size_bytes=1024,
        sha256=hashlib.sha256(b"synthetic").hexdigest(),
        page_count=None,
        created_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return Document(**defaults)


def _mock_openrouter(response_payload: dict) -> httpx.MockTransport:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/chat/completions"
        assert request.headers["Authorization"] == "Bearer synthetic-openrouter-key"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(response_payload)}}],
                "usage": {"total_tokens": 42},
            },
        )

    return httpx.MockTransport(handler)


@pytest.mark.anyio
async def test_extractor_resolves_evidence_ids_and_drops_unanchored_items() -> None:
    storage = InMemoryDocumentStorage()
    document = _make_document()
    content = _make_pdf("Beneficiarul trebuie sa raporteze trimestrial progresul proiectului.")
    handle = await storage.put(document.id, content)

    response_payload = {
        "criteria": [
            {
                "code": "CRIT-01",
                "description": "Raportare trimestriala a progresului.",
                "deadline": "2030-06-30",
                "evidenceIds": ["D0_P1_0"],
            },
            {
                "code": "CRIT-02",
                "description": "Criteriu fara ancora valida.",
                "deadline": None,
                "evidenceIds": ["UNKNOWN_ID"],
            },
        ]
    }
    transport = _mock_openrouter(response_payload)
    client = httpx.AsyncClient(base_url="https://openrouter.test", transport=transport)
    try:
        extractor = OpenRouterCriterionExtractor(
            document_storage=storage,
            api_key="synthetic-openrouter-key",
            model="synthetic-model",
            base_url="https://openrouter.test",
            client=client,
        )
        request = CriterionExtractionRequest(
            job_id=uuid4(),
            project_id=document.project_id,
            documents=(AIInputDocument(metadata=document, content_handle=handle),),
            idempotency_key="synthetic-extract-key",
        )
        proposals = await extractor.extract(request)
    finally:
        await client.aclose()

    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.code == "CRIT-01"
    assert proposal.deadline is not None and proposal.deadline.isoformat() == "2030-06-30"
    assert len(proposal.source_anchors) == 1
    anchor = proposal.source_anchors[0]
    assert anchor.document_id == document.id
    assert anchor.page_number == 1
    assert "trimestrial" in anchor.passage


@pytest.mark.anyio
async def test_analyzer_returns_exactly_one_result_per_criterion() -> None:
    storage = InMemoryDocumentStorage()
    report_document = _make_document()
    content = _make_pdf("Raportul confirma finalizarea activitatii de instruire pentru personal.")
    handle = await storage.put(report_document.id, content)

    from app.models.domain import Criterion

    covered_criterion = Criterion(
        id=uuid4(),
        project_id=report_document.project_id,
        code="CRIT-01",
        description="Instruirea personalului trebuie finalizata.",
        deadline=None,
        source_anchors=[],
        version=1,
        active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    uncovered_criterion = covered_criterion.model_copy(
        update={"id": uuid4(), "code": "CRIT-02", "description": "Criteriu neabordat de model."}
    )

    report = Report(
        id=uuid4(),
        project_id=report_document.project_id,
        report_type=ReportType.DURABILITY,
        period_start=datetime(2030, 1, 1).date(),
        period_end=datetime(2030, 12, 31).date(),
        documents=[
            ReportDocument(document_id=report_document.id, role=ReportDocumentRole.MAIN_REPORT)
        ],
        external_system=None,
        external_id=None,
        external_url=None,
        external_status=None,
        status=ReportStatus.CREATED,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    response_payload = {
        "validations": [
            {
                "criterionIndex": 1,
                "outcome": "compliant",
                "rationale": "Raportul confirma finalizarea instruirii.",
                "evidenceIds": ["D0_P1_0"],
            }
        ]
    }
    transport = _mock_openrouter(response_payload)
    client = httpx.AsyncClient(base_url="https://openrouter.test", transport=transport)
    try:
        analyzer = OpenRouterReportAnalyzer(
            document_storage=storage,
            api_key="synthetic-openrouter-key",
            model="synthetic-model",
            base_url="https://openrouter.test",
            client=client,
        )
        request = ReportAnalysisRequest(
            job_id=uuid4(),
            project_id=report_document.project_id,
            report=report,
            criteria=(covered_criterion, uncovered_criterion),
            project_documents=(),
            previous_reports=(),
            allowed_documents=(AIInputDocument(metadata=report_document, content_handle=handle),),
            idempotency_key="synthetic-analysis-key",
        )
        results = await analyzer.analyze(request)
    finally:
        await client.aclose()

    assert len(results) == 2
    by_id = {item.criterion_id: item for item in results}

    covered_result = by_id[covered_criterion.id]
    assert covered_result.outcome == AIOutcome.COMPLIANT
    assert len(covered_result.source_anchors) == 1
    assert covered_result.source_anchors[0].document_id == report_document.id

    fallback_result = by_id[uncovered_criterion.id]
    assert fallback_result.outcome == AIOutcome.INSUFFICIENT_EVIDENCE
    assert fallback_result.source_anchors == ()


@pytest.mark.anyio
async def test_provider_failure_raises_unavailable_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(500, text="provider error")

    storage = InMemoryDocumentStorage()
    document = _make_document()
    handle = await storage.put(document.id, _make_pdf("Text sintetic."))
    client = httpx.AsyncClient(
        base_url="https://openrouter.test", transport=httpx.MockTransport(handler)
    )
    try:
        extractor = OpenRouterCriterionExtractor(
            document_storage=storage,
            api_key="synthetic-openrouter-key",
            model="synthetic-model",
            base_url="https://openrouter.test",
            client=client,
        )
        request = CriterionExtractionRequest(
            job_id=uuid4(),
            project_id=document.project_id,
            documents=(AIInputDocument(metadata=document, content_handle=handle),),
            idempotency_key="synthetic-extract-key",
        )
        with pytest.raises(OpenRouterUnavailableError):
            await extractor.extract(request)
    finally:
        await client.aclose()
