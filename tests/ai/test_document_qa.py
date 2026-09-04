from uuid import uuid4

import pytest

from AI.document_parser import ParsedDocument, ParsedPage, StructuredBlock
from AI.document_qa import (
    OpenRouterDocumentQuestionAnswerer,
    _GroundedCandidate,
)
from AI.retrieval import Chunk, chunk_documents
from AI.source_units import source_units
from app.services.ports import AIResponseValidationError


def test_answer_is_reconstructed_from_exact_local_units() -> None:
    document_id = uuid4()
    source = "Contribuția proprie selectată pentru proiect este 20%."
    chunk = Chunk(document_id, 7, 0, len(source), source)
    candidate = _GroundedCandidate("C1", chunk, source, source_units(source))

    answer = OpenRouterDocumentQuestionAnswerer._validated_answer(
        {
            "status": "found",
            "matches": [
                {
                    "candidate_id": "C1",
                    "unit_start": 0,
                    "unit_end": 0,
                    "value": "20%",
                }
            ],
        },
        [candidate],
    )

    assert answer.status == "found"
    assert answer.matches[0].value == "20%"
    assert answer.matches[0].source_anchor.passage == source
    assert answer.matches[0].source_anchor.page_number == 7


def test_answer_rejects_value_not_present_in_evidence() -> None:
    document_id = uuid4()
    source = "Valoarea eligibilă este 100 RON."
    candidate = _GroundedCandidate(
        "C1",
        Chunk(document_id, 2, 0, len(source), source),
        source,
        source_units(source),
    )

    with pytest.raises(AIResponseValidationError):
        OpenRouterDocumentQuestionAnswerer._validated_answer(
            {
                "status": "found",
                "matches": [
                    {
                        "candidate_id": "C1",
                        "unit_start": 0,
                        "unit_end": 0,
                        "value": "999 RON",
                    }
                ],
            },
            [candidate],
        )


def test_question_index_can_include_raw_option_page_without_changing_extraction_default() -> None:
    document_id = uuid4()
    page = ParsedPage(
        document_id=document_id,
        page_number=1,
        text="Selectată: Da\nContribuție 20%\nSelectată: Nu\nContribuție 10%",
        blocks=(
            StructuredBlock(
                text="Contribuție 20% Selectată: Da",
                kind="selected_option",
                source_text="Selectată: Da\nContribuție 20%",
            ),
        ),
        prefer_structured=True,
    )
    document = ParsedDocument(document_id, (page,))

    extraction_chunks = chunk_documents((document,))
    question_chunks = chunk_documents((document,), include_prefer_structured_raw=True)

    assert all(chunk.kind != "text" for chunk in extraction_chunks)
    assert any(
        chunk.kind == "text" and "Contribuție 10%" in chunk.text
        for chunk in question_chunks
    )
