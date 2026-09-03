from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

np = pytest.importorskip("numpy")

from AI.document_parser import ParsedDocument, ParsedPage
from AI.qwen_adapter import QwenAIAdapter
from app.models.domain import (
    AIOutcome,
    Criterion,
    Document,
    DocumentMediaType,
    Report,
    ReportDocument,
    ReportDocumentRole,
    ReportStatus,
    ReportType,
    SourceAnchor,
)
from app.services.ports import AIInputDocument, CriterionExtractionRequest, ReportAnalysisRequest


class StubEmbedder:
    def encode_passages(self, texts: list[str]):
        # Dense semantic component is injected for unit tests; production uses E5.
        return np.ones((len(texts), 3), dtype=np.float32)

    def encode_query(self, query: str):
        return np.ones(3, dtype=np.float32)


class StubLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def json_chat(self, *, system: str, user: str, **_: object):
        self.calls += 1
        if '"proposals"' in system:
            return {
                "proposals": [
                    {
                        "candidate_id": "E1",
                        "unit_start": 0,
                        "unit_end": 0,
                        "deadline": "2031-06-30",
                    }
                ]
            }
        return {
            "validations": [
                {
                    "criterion_id": str(self.criterion_id),
                    "outcome": "non_compliant",
                    "rationale": "Valoarea raportată diferă de criteriul aprobat.",
                    "evidence": [
                        {
                            "candidate_id": "C1E1",
                            "unit_start": 0,
                            "unit_end": 0,
                        }
                    ],
                }
            ]
        }


@pytest.mark.asyncio
async def test_qwen_adapter_uses_exact_local_source_text(monkeypatch):
    project_id = uuid4()
    source_id = uuid4()
    report_id = uuid4()
    report_document_id = uuid4()
    now = datetime.now(UTC)

    source_text = "Beneficiarul va menține trei locuri de muncă până la 30.06.2031.\nAlt text."
    report_text = "Raportul declară doar două locuri de muncă menținute în perioada analizată."

    source_document = Document(
        id=source_id,
        project_id=project_id,
        display_name="Contract",
        original_filename="contract.pdf",
        media_type=DocumentMediaType.PDF,
        size_bytes=100,
        sha256="a" * 64,
        page_count=1,
        created_at=now,
    )
    report_document = Document(
        id=report_document_id,
        project_id=project_id,
        display_name="Raport",
        original_filename="report.pdf",
        media_type=DocumentMediaType.PDF,
        size_bytes=100,
        sha256="b" * 64,
        page_count=1,
        created_at=now,
    )

    parsed_by_id = {
        source_id: ParsedDocument(source_id, (ParsedPage(source_id, 1, source_text),)),
        report_document_id: ParsedDocument(
            report_document_id,
            (ParsedPage(report_document_id, 1, report_text),),
        ),
    }

    def fake_parse(document_id, media_type, content):
        return parsed_by_id[document_id]

    monkeypatch.setattr("AI.qwen_adapter.parse_document_bytes", fake_parse)

    async def loader(handle: str):
        return handle.encode()

    llm = StubLLM()
    adapter = QwenAIAdapter(
        content_loader=loader,
        model="qwen/qwen3-235b-a22b-2507",
        base_url="https://example.invalid/api/v1",
        api_key="synthetic-key",
        llm=llm,
        embedder=StubEmbedder(),
    )

    extraction = await adapter.extract(
        CriterionExtractionRequest(
            job_id=uuid4(),
            project_id=project_id,
            documents=(AIInputDocument(source_document, "source"),),
            idempotency_key="synthetic-extraction",
        )
    )
    assert len(extraction) == 1
    assert extraction[0].description == "Beneficiarul va menține trei locuri de muncă până la 30.06.2031."
    assert extraction[0].source_anchors[0].passage == extraction[0].description
    assert extraction[0].source_anchors[0].page_number == 1

    criterion = Criterion(
        id=uuid4(),
        project_id=project_id,
        code=extraction[0].code,
        description=extraction[0].description,
        deadline=date(2031, 6, 30),
        source_anchors=list(extraction[0].source_anchors),
        version=1,
        active=True,
        created_at=now,
        updated_at=now,
    )
    llm.criterion_id = criterion.id
    report = Report(
        id=report_id,
        project_id=project_id,
        report_type=ReportType.DURABILITY,
        period_start=date(2031, 1, 1),
        period_end=date(2031, 12, 31),
        documents=[
            ReportDocument(
                document_id=report_document_id,
                role=ReportDocumentRole.MAIN_REPORT,
            )
        ],
        external_system=None,
        external_id=None,
        external_url=None,
        external_status=None,
        status=ReportStatus.CREATED,
        created_at=now,
        updated_at=now,
    )

    result = await adapter.analyze(
        ReportAnalysisRequest(
            job_id=uuid4(),
            project_id=project_id,
            report=report,
            criteria=(criterion,),
            project_documents=(AIInputDocument(source_document, "source"),),
            previous_reports=(),
            allowed_documents=(
                AIInputDocument(source_document, "source"),
                AIInputDocument(report_document, "report"),
            ),
            idempotency_key="synthetic-analysis",
        )
    )
    assert len(result) == 1
    assert result[0].outcome == AIOutcome.NON_COMPLIANT
    assert result[0].source_anchors
    assert result[0].source_anchors[0].document_id == report_document_id
    assert result[0].source_anchors[0].passage in report_text


@pytest.mark.asyncio
async def test_progress_report_never_creates_obligation_proposals(monkeypatch):
    project_id = uuid4()
    report_document_id = uuid4()
    now = datetime.now(UTC)
    report_document = Document(
        id=report_document_id,
        project_id=project_id,
        display_name="Rapoarte de progres",
        original_filename="raport-progres.pdf",
        media_type=DocumentMediaType.PDF,
        size_bytes=100,
        sha256="c" * 64,
        page_count=1,
        created_at=now,
    )

    def unexpected_parse(*args, **kwargs):
        raise AssertionError("A progress report must not enter obligation extraction")

    monkeypatch.setattr("AI.qwen_adapter.parse_document_bytes", unexpected_parse)

    async def loader(handle: str):
        return handle.encode()

    llm = StubLLM()
    adapter = QwenAIAdapter(
        content_loader=loader,
        model="qwen/qwen3-235b-a22b-2507",
        base_url="https://example.invalid/api/v1",
        api_key="synthetic-key",
        llm=llm,
        embedder=StubEmbedder(),
    )

    result = await adapter.extract(
        CriterionExtractionRequest(
            job_id=uuid4(),
            project_id=project_id,
            documents=(AIInputDocument(report_document, "report"),),
            idempotency_key="synthetic-progress-report",
        )
    )

    assert result == []
    assert llm.calls == 0
