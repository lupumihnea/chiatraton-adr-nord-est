from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

np = pytest.importorskip("numpy")

from AI.document_parser import ParsedDocument, ParsedPage  # noqa: E402
from AI.qwen_adapter import QwenAIAdapter  # noqa: E402
from app.models.domain import (  # noqa: E402
    AIOutcome,
    Criterion,
    Document,
    DocumentMediaType,
    Report,
    ReportDocument,
    ReportDocumentRole,
    ReportStatus,
    ReportType,
)
from app.services.ports import (  # noqa: E402
    AIInputDocument,
    CriterionExtractionRequest,
    ReportAnalysisRequest,
)


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
        if '"claims"' in system:
            assert "CANDIDATE E1" in user
            return {
                "claims": [
                    {
                        "claim_ref": "C1",
                        "statement": (
                            "Beneficiarul va menține trei locuri de muncă "
                            "până la 30.06.2031."
                        ),
                        "evidence": [
                            {
                                "candidate_id": "E1",
                                "unit_start": 0,
                                "unit_end": 0,
                            }
                        ],
                        "deadline": "2031-06-30",
                    }
                ],
                "coverage": [
                    {
                        "candidate_id": "E1",
                        "status": "claimed",
                        "claim_refs": ["C1"],
                    }
                ],
            }
        if '"reviews"' in system:
            assert "CLAIM K1" in user
            return {
                "reviews": [
                    {
                        "claim_id": "K1",
                        "decision": "keep",
                        "classification": "maintained_project_condition",
                        "baseline_failure": (
                            "Cele trei locuri de muncă nu sunt menținute până la termen."
                        ),
                        "evidence_sufficient": True,
                        "reason": "Dovada definește o stare menținută și un termen.",
                    }
                ]
            }
        if '"selected_claim_ids"' in system:
            assert "PROVISIONAL CLAIM K1" in user
            return {"selected_claim_ids": ["K1"]}
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

    expected_source_text = (
        "Beneficiarul va menține trei locuri de muncă până la 30.06.2031."
    )
    source_text = f"{expected_source_text}\nAlt text."
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
    assert extraction[0].description == (
        "Beneficiarul va menține trei locuri de muncă până la 30.06.2031."
    )
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


@pytest.mark.asyncio
async def test_extraction_rejects_orphaned_numeric_date_and_label_fragments(monkeypatch):
    project_id = uuid4()
    document_id = uuid4()
    now = datetime.now(UTC)
    source_text = "\n".join(
        [
            "1.199.159,44 RON",
            "08-2024 11-2024",
            "FEDR - Fondul European de Dezvoltare Regională",
            "Contribuția solicitantului la valoarea cheltuielilor eligibile 20%",
            (
                "30-09-2024 Publicarea si transmiterea anunțului pentru "
                "procedurile de achiziții"
            ),
        ]
    )

    monkeypatch.setattr(
        "AI.qwen_adapter.parse_document_bytes",
        lambda *_args, **_kwargs: ParsedDocument(
            document_id, (ParsedPage(document_id, 1, source_text),)
        ),
    )

    class FragmentLLM:
        async def json_chat(self, *, system: str, user: str, **_: object):
            if '"claims"' in system:
                assert "CANDIDATE E1" in user
                claim_rows = [
                    ("C1", 0, "Valoarea bugetară este 1.199.159,44 RON."),
                    ("C2", 1, "Intervalul calendaristic este 08-2024 - 11-2024."),
                    (
                        "C3",
                        2,
                        "Finanțarea este din Fondul European de Dezvoltare Regională.",
                    ),
                    (
                        "C4",
                        3,
                        (
                            "Contribuția solicitantului la valoarea "
                            "cheltuielilor eligibile este 20%."
                        ),
                    ),
                    (
                        "C5",
                        4,
                        (
                            "Anunțul pentru procedurile de achiziții trebuie "
                            "publicat și transmis până la 30-09-2024."
                        ),
                    ),
                ]
                return {
                    "claims": [
                        {
                            "claim_ref": claim_ref,
                            "statement": statement,
                            "evidence": [
                                {
                                    "candidate_id": "E1",
                                    "unit_start": unit,
                                    "unit_end": unit,
                                }
                            ],
                            "deadline": None,
                        }
                        for claim_ref, unit, statement in claim_rows
                    ],
                    "coverage": [
                        {
                            "candidate_id": "E1",
                            "status": "claimed",
                            "claim_refs": [row[0] for row in claim_rows],
                        }
                    ],
                }

            if '"reviews"' in system:
                assert "budget_or_accounting_attribute" in system
                assert "CLAIM K1" in user
                rows = [
                    (
                        "K1",
                        "keep",
                        "quantified_target",
                        "Valoarea bugetară nu este respectată.",
                    ),
                    (
                        "K2",
                        "keep",
                        "dated_milestone",
                        "Intervalul calendaristic nu este respectat.",
                    ),
                    (
                        "K3",
                        "keep",
                        "selected_project_condition",
                        "Sursa de finanțare nu este menținută.",
                    ),
                    (
                        "K4",
                        "keep",
                        "beneficiary_financial_contribution",
                        "Beneficiarul nu asigură contribuția proprie de 20%.",
                    ),
                    (
                        "K5",
                        "keep",
                        "dated_milestone",
                        "Anunțul nu este publicat și transmis până la termen.",
                    ),
                ]
                return {
                    "reviews": [
                        {
                            "claim_id": claim_id,
                            "decision": decision,
                            "classification": classification,
                            "baseline_failure": baseline_failure,
                            "evidence_sufficient": True,
                            "reason": "Clasificare semantică de test.",
                        }
                        for claim_id, decision, classification, baseline_failure in rows
                    ]
                }

            assert '"selected_claim_ids"' in system
            assert "PROVISIONAL CLAIM K1" in user
            assert "PROVISIONAL CLAIM K5" in user
            return {"selected_claim_ids": ["K4", "K5"]}

    async def loader(handle: str):
        return handle.encode()

    document = Document(
        id=document_id,
        project_id=project_id,
        display_name="Documente inițiale",
        original_filename="baseline.pdf",
        media_type=DocumentMediaType.PDF,
        size_bytes=100,
        sha256="f" * 64,
        page_count=1,
        created_at=now,
    )
    adapter = QwenAIAdapter(
        content_loader=loader,
        model="qwen/qwen3-235b-a22b-2507",
        base_url="https://example.invalid/api/v1",
        api_key="synthetic-key",
        llm=FragmentLLM(),
        embedder=StubEmbedder(),
    )

    result = await adapter.extract(
        CriterionExtractionRequest(
            job_id=uuid4(),
            project_id=project_id,
            documents=(AIInputDocument(document, "baseline"),),
            idempotency_key="fragment-filtering",
        )
    )

    assert [item.description for item in result] == [
        "Contribuția solicitantului la valoarea cheltuielilor eligibile este 20%.",
        (
            "Anunțul pentru procedurile de achiziții trebuie publicat și "
            "transmis până la 30-09-2024."
        ),
    ]


def test_structured_anchor_uses_canonical_source_not_semantic_serialization():
    from AI.retrieval import Chunk

    document_id = uuid4()
    semantic = "Nume reper: Raport final | Termen: 23-07-2025"
    exact = "Raport final\n23-07-2025"
    chunk = Chunk(
        document_id=document_id,
        page_number=33,
        start=0,
        end=len(semantic),
        text=semantic,
        kind="table_row",
        source_text=exact,
    )
    candidate = QwenAIAdapter._candidate(chunk, "E1")
    assert candidate is not None

    anchor = QwenAIAdapter._anchor(candidate, 0, 0)
    assert anchor.document_id == document_id
    assert anchor.page_number == 33
    assert anchor.passage == "Raport final"
    assert "Nume reper:" not in anchor.passage

    full_anchor = QwenAIAdapter._anchor(candidate, 0, 1)
    assert full_anchor.passage == exact


def test_structured_anchor_can_slice_exact_source_units_atomically():
    from AI.retrieval import Chunk

    document_id = uuid4()
    semantic = (
        "Luna estimată: august 2024 | Denumire: achizitie 1 | "
        "Valoare: 198.936,39 | Denumire: Electrostivuitor | Valoare: 263.379,87"
    )
    exact = (
        "august 2024\n"
        "achizitie 1\n"
        "198.936,39\n"
        "Electrostivuitor\n"
        "263.379,87"
    )
    chunk = Chunk(
        document_id=document_id,
        page_number=12,
        start=0,
        end=len(semantic),
        text=semantic,
        kind="table_row",
        source_text=exact,
    )

    candidate = QwenAIAdapter._candidate(chunk, "E1")
    assert candidate is not None
    formatted = QwenAIAdapter._format_candidate(candidate)
    assert "SEMANTIC STRUCTURE:" in formatted
    assert "Denumire: achizitie 1" in formatted
    assert "U1: achizitie 1" in formatted

    first = QwenAIAdapter._anchor(candidate, 0, 2)
    second = QwenAIAdapter._anchor(candidate, 3, 4)

    assert first.passage == "august 2024\nachizitie 1\n198.936,39"
    assert second.passage == "Electrostivuitor\n263.379,87"


@pytest.mark.asyncio
async def test_report_factual_outcome_requires_current_report_match(monkeypatch):
    project_id = uuid4()
    source_id = uuid4()
    report_document_id = uuid4()
    now = datetime.now(UTC)

    source_text = "Beneficiarul trebuie să mențină trei locuri de muncă."
    report_text = "Raportul descrie alte activități fără informații despre locurile de muncă."
    source_document = Document(
        id=source_id,
        project_id=project_id,
        display_name="Documente inițiale",
        original_filename="cerere.pdf",
        media_type=DocumentMediaType.PDF,
        size_bytes=100,
        sha256="d" * 64,
        page_count=1,
        created_at=now,
    )
    report_document = Document(
        id=report_document_id,
        project_id=project_id,
        display_name="Rapoarte de progres",
        original_filename="raport.pdf",
        media_type=DocumentMediaType.PDF,
        size_bytes=100,
        sha256="e" * 64,
        page_count=1,
        created_at=now,
    )
    parsed_by_id = {
        source_id: ParsedDocument(source_id, (ParsedPage(source_id, 1, source_text),)),
        report_document_id: ParsedDocument(
            report_document_id, (ParsedPage(report_document_id, 1, report_text),)
        ),
    }
    monkeypatch.setattr(
        "AI.qwen_adapter.parse_document_bytes",
        lambda document_id, media_type, content: parsed_by_id[document_id],
    )

    class BaselineOnlyLLM:
        async def json_chat(self, *, system: str, user: str, **_: object):
            return {
                "validations": [
                    {
                        "criterion_id": str(criterion.id),
                        "outcome": "compliant",
                        "rationale": "Baseline-ul descrie obligația.",
                        "evidence": [
                            {"candidate_id": "C1E2", "unit_start": 0, "unit_end": 0}
                        ],
                    }
                ]
            }

    async def loader(handle: str):
        return handle.encode()

    criterion = Criterion(
        id=uuid4(),
        project_id=project_id,
        code="JOB-3",
        description=source_text,
        deadline=None,
        source_anchors=[
            SourceAnchor(document_id=source_id, page_number=1, passage=source_text)
        ],
        version=1,
        active=True,
        created_at=now,
        updated_at=now,
    )
    report = Report(
        id=uuid4(),
        project_id=project_id,
        report_type=ReportType.DURABILITY,
        period_start=date(2031, 1, 1),
        period_end=date(2031, 3, 31),
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
    adapter = QwenAIAdapter(
        content_loader=loader,
        model="qwen/qwen3-235b-a22b-2507",
        base_url="https://example.invalid/api/v1",
        api_key="synthetic-key",
        llm=BaselineOnlyLLM(),
        embedder=StubEmbedder(),
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
                AIInputDocument(report_document, "report"),
                AIInputDocument(source_document, "source"),
            ),
            idempotency_key="current-report-match-required",
        )
    )

    assert result[0].outcome == AIOutcome.INSUFFICIENT_EVIDENCE
    assert result[0].source_anchors == ()
