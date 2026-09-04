from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from AI.document_parser import ParsedDocument, ParsedPage
from AI.qwen_adapter import QwenAIAdapter
from app.models.domain import Document, DocumentMediaType
from app.services.ports import AIInputDocument, CriterionExtractionRequest


class GlobalCompilerLLM:
    async def json_chat(self, *, system: str, user: str, **_: object):
        if '"claims"' in system:
            assert "DISCOVERY RUBRIC (NOT KEYWORD RULES)" in system
            assert "beneficiary's own contribution" in system
            assert "CANDIDATE E1" in user
            assert "CANDIDATE E2" in user
            return {
                "claims": [
                    {
                        "claim_ref": "C1",
                        "statement": "Beneficiarul va crea trei locuri de muncă.",
                        "evidence": [
                            {
                                "candidate_id": "E1",
                                "unit_start": 0,
                                "unit_end": 0,
                            }
                        ],
                        "deadline": None,
                    },
                    {
                        "claim_ref": "C2",
                        "statement": "Beneficiarul va instala un sistem fotovoltaic.",
                        "evidence": [
                            {
                                "candidate_id": "E1",
                                "unit_start": 1,
                                "unit_end": 1,
                            }
                        ],
                        "deadline": None,
                    },
                    {
                        "claim_ref": "C3",
                        "statement": "Beneficiarul va crea trei locuri de muncă.",
                        "evidence": [
                            {
                                "candidate_id": "E2",
                                "unit_start": 0,
                                "unit_end": 0,
                            }
                        ],
                        "deadline": None,
                    },
                ],
                "coverage": [
                    {
                        "candidate_id": "E1",
                        "status": "claimed",
                        "claim_refs": ["C1", "C2"],
                    },
                    {
                        "candidate_id": "E2",
                        "status": "claimed",
                        "claim_refs": ["C3"],
                    },
                ],
            }

        if '"reviews"' in system:
            assert "Return exactly one verdict" in system
            assert "CLAIM K1" in user
            assert "CLAIM K2" in user
            return {
                "reviews": [
                    {
                        "claim_id": claim_id,
                        "decision": "keep",
                        "classification": classification,
                        "baseline_failure": baseline_failure,
                        "evidence_sufficient": True,
                        "reason": "Afirmația definește un rezultat verificabil.",
                    }
                    for claim_id, classification, baseline_failure in [
                        (
                            "K1",
                            "quantified_target",
                            "Cele trei locuri de muncă nu sunt create.",
                        ),
                        (
                            "K2",
                            "committed_project_output",
                            "Sistemul fotovoltaic nu este instalat.",
                        ),
                    ]
                ]
            }

        assert '"selected_claim_ids"' in system
        assert "PROVISIONAL CLAIM K1" in user
        assert "PROVISIONAL CLAIM K2" in user
        return {"selected_claim_ids": ["K1", "K2"]}


@pytest.mark.asyncio
async def test_global_compiler_splits_composite_and_merges_duplicate_evidence(monkeypatch):
    project_id = uuid4()
    document_id = uuid4()
    now = datetime.now(UTC)
    composite = (
        "Beneficiarul va crea trei locuri de muncă - "
        "Beneficiarul va instala un sistem fotovoltaic"
    )
    duplicate = "Beneficiarul va crea trei locuri de muncă"
    parsed = ParsedDocument(
        document_id,
        (
            ParsedPage(document_id, 1, composite),
            ParsedPage(document_id, 2, duplicate),
        ),
    )

    monkeypatch.setattr(
        "AI.qwen_adapter.parse_document_bytes",
        lambda *_args, **_kwargs: parsed,
    )

    async def loader(_handle: str):
        return b"synthetic"

    document = Document(
        id=document_id,
        project_id=project_id,
        display_name="Documente inițiale",
        original_filename="baseline.pdf",
        media_type=DocumentMediaType.PDF,
        size_bytes=100,
        sha256="d" * 64,
        page_count=2,
        created_at=now,
    )
    adapter = QwenAIAdapter(
        content_loader=loader,
        model="qwen/qwen3-235b-a22b-2507",
        base_url="https://example.invalid/api/v1",
        api_key="synthetic-key",
        llm=GlobalCompilerLLM(),
    )

    result = await adapter.extract(
        CriterionExtractionRequest(
            job_id=uuid4(),
            project_id=project_id,
            documents=(AIInputDocument(document, "baseline"),),
            idempotency_key="synthetic-global-compiler",
        )
    )

    assert len(result) == 2
    assert result[0].description == "Beneficiarul va crea trei locuri de muncă."
    assert len(result[0].source_anchors) == 2
    assert {anchor.page_number for anchor in result[0].source_anchors} == {1, 2}
    assert result[1].description == "Beneficiarul va instala un sistem fotovoltaic."
