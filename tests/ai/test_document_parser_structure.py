import json
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import AI.document_parser as document_parser
from AI.document_parser import (
    ParsedDocument,
    ParsedPage,
    StructuredBlock,
    _row_text,
    _selected_option_blocks,
)
from AI.retrieval import chunk_documents


def test_table_row_keeps_header_cell_relationships() -> None:
    text = _row_text(
        ["Nume reper", "Descriere", "Termen"],
        [
            "Finalizarea contractului de furnizare",
            "Receptionarea echipamentelor",
            "23-07-2025",
        ],
    )
    assert text == (
        "Nume reper: Finalizarea contractului de furnizare | "
        "Descriere: Receptionarea echipamentelor | Termen: 23-07-2025"
    )


def test_selected_options_drop_only_unselected_alternatives() -> None:
    pages = [
        """
Descriere subcriteriu:
1.3 Cresterea numarului mediu de salariati ca urmare a realizarii investitiei
Tip: OPTIUNI
Descriere:
a. Investiția prevede creșterea numărului mediu de salariați cu mai mult de 2
și menținerea acestei creșteri pe perioada de monitorizare
; 10,00; Da
Punctaj:
Selectată:
Descriere:
b. Investiția prevede creșterea numărului mediu de salariați cu 2
; 5,00; Nu
Punctaj:
Selectată:
""",
        """
Descriere subcriteriu:
3.1 Rata solvabilităţii generale a microîntreprinderii pe anul fiscal anterior
depunerii cererii de finantare
Tip: OPTIUNI
Descriere:
a. RSG >=2
; 5,00; Da
Punctaj:
Selectată:
""",
    ]
    blocks, option_pages = _selected_option_blocks(pages)

    assert option_pages == {1, 2}
    assert len(blocks[1]) == 1
    assert "mai mult de 2" in blocks[1][0].text
    assert "cu 2" not in blocks[1][0].text
    # The parser is structural, not semantic: the global compiler decides
    # whether this selected evaluation fact is monitorable.
    assert len(blocks[2]) == 1
    assert "RSG >=2" in blocks[2][0].text


def test_selected_option_context_continues_across_pages() -> None:
    pages = [
        """
Descriere subcriteriu:
3.2 Contribuția solicitantului la valoarea cheltuielilor eligibile.
Tip: OPTIUNI
Descriere:
a1 Contribuția solicitantului la valoarea cheltuielilor eligibile 11%
; 1,00; Nu
Punctaj:
Selectată:
""",
        """
Descriere:
a10 Contribuția solicitantului la valoarea cheltuielilor eligibile 20%
; 10,00; Da
Punctaj:
Selectată:
Descriere:
b. Contribuția solicitantului la valoarea cheltuielilor eligibile 10%
; 0,00; Nu
Punctaj:
Selectată:
""",
    ]
    blocks, option_pages = _selected_option_blocks(pages)

    assert option_pages == {1, 2}
    assert len(blocks[2]) == 1
    assert "20%" in blocks[2][0].text
    assert "11%" not in blocks[2][0].text
    assert "Selectată:" in blocks[2][0].source_text
    assert "Da" in blocks[2][0].source_text


def test_binary_selected_option_source_includes_context_and_selected_yes() -> None:
    pages = [
        """
Descriere subcriteriu:
Investiția este localizată într-o zonă eligibilă?
Tip: OPTIUNI
Descriere:
a. Da
; 5,00; Da
Punctaj:
Selectată:
Descriere:
b. Nu
; 0,00; Nu
Punctaj:
Selectată:
""",
    ]
    blocks, option_pages = _selected_option_blocks(pages)

    assert option_pages == {1}
    assert len(blocks[1]) == 1
    assert "localizată" in blocks[1][0].text
    assert "Opțiune selectată: a. Da" in blocks[1][0].text
    assert "Investiția este localizată într-o zonă eligibilă?" in blocks[1][0].source_text
    assert "a. Da" in blocks[1][0].source_text
    assert "Selectată:" in blocks[1][0].source_text


def test_option_page_raw_text_is_not_chunked_back_into_candidates() -> None:
    document_id = uuid4()
    page = ParsedPage(
        document_id=document_id,
        page_number=1,
        text="SELECTED GOOD\nUNSELECTED BAD Selectată: Nu",
        blocks=(
            StructuredBlock(
                "SELECTED GOOD\nPunctaj: 10; Selectată: Da",
                "selected_option",
                source_text="SELECTED GOOD",
            ),
        ),
        prefer_structured=True,
    )
    chunks = chunk_documents((ParsedDocument(document_id, (page,)),))

    assert len(chunks) == 1
    assert chunks[0].kind == "selected_option"
    assert "UNSELECTED BAD" not in chunks[0].text


def test_structured_block_keeps_semantic_text_separate_from_exact_source() -> None:
    document_id = uuid4()
    exact = "Demararea achiziției\n30-09-2024\nContract semnat"
    page = ParsedPage(
        document_id=document_id,
        page_number=4,
        text=f"Alt text\n{exact}\nFinal",
        blocks=(
            StructuredBlock(
                text=(
                    "Nume reper: Demararea achiziției | Termen: 30-09-2024 | "
                    "Dovadă: Contract semnat"
                ),
                kind="table_row",
                source_text=exact,
                source_page_number=4,
            ),
        ),
    )
    chunks = chunk_documents((ParsedDocument(document_id, (page,)),))
    structured = next(chunk for chunk in chunks if chunk.kind == "table_row")

    assert structured.text != exact
    assert structured.source_text == exact
    assert structured.source_text in page.text


def test_structured_block_without_exact_source_is_not_exposed_to_llm() -> None:
    document_id = uuid4()
    page = ParsedPage(
        document_id=document_id,
        page_number=1,
        text="Indicator RCR02 și termen 23-07-2025.",
        blocks=(
            StructuredBlock(
                "Indicator: RCR02 | Termen: 23-07-2025",
                "table_row",
                source_text=None,
            ),
        ),
    )
    chunks = chunk_documents((ParsedDocument(document_id, (page,)),))

    assert all(chunk.kind != "table_row" for chunk in chunks)
    assert any(chunk.kind == "text" and "RCR02" in chunk.text for chunk in chunks)


def test_structured_block_with_noncanonical_source_is_not_exposed_to_llm() -> None:
    document_id = uuid4()
    page = ParsedPage(
        document_id=document_id,
        page_number=7,
        text="Textul canonic real al paginii.",
        blocks=(
            StructuredBlock(
                text="Coloană: valoare",
                kind="table_row",
                source_text="text inventat care nu există în pagină",
                source_page_number=7,
            ),
        ),
    )
    chunks = chunk_documents((ParsedDocument(document_id, (page,)),))

    assert all(chunk.kind != "table_row" for chunk in chunks)
    assert any(chunk.kind == "text" for chunk in chunks)


def test_opendataloader_hybrid_options_are_forwarded(monkeypatch) -> None:
    calls: dict[str, object] = {}

    def fake_convert(**kwargs) -> None:
        calls.update(kwargs)
        output_dir = Path(str(kwargs["output_dir"]))
        payload = {
            "kids": [
                {
                    "type": "table",
                    "page number": 1,
                    "rows": [
                        {
                            "type": "table row",
                            "cells": [
                                {
                                    "column number": 1,
                                    "kids": [{"content": "Header"}],
                                }
                            ],
                        },
                        {
                            "type": "table row",
                            "cells": [
                                {
                                    "column number": 1,
                                    "kids": [{"content": "Value"}],
                                }
                            ],
                        },
                    ],
                }
            ]
        }
        (output_dir / "document.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )

    monkeypatch.setenv("CHIATRATON_PDF_OPENDATALOADER_HYBRID", "docling-fast")
    monkeypatch.setenv("CHIATRATON_PDF_OPENDATALOADER_HYBRID_MODE", "auto")
    monkeypatch.setenv("CHIATRATON_PDF_OPENDATALOADER_HYBRID_TIMEOUT", "60000")
    monkeypatch.setattr(document_parser.shutil, "which", lambda name: "java")
    monkeypatch.setitem(
        sys.modules, "opendataloader_pdf", SimpleNamespace(convert=fake_convert)
    )

    blocks = document_parser._opendataloader_table_blocks(
        b"%PDF", {1: "Intro\nValue\nEnd"}
    )

    assert calls["hybrid"] == "docling-fast"
    assert calls["hybrid_mode"] == "auto"
    assert calls["hybrid_fallback"] is True
    assert calls["hybrid_timeout"] == "60000"
    assert blocks[1][0].text == "Header: Value"
    assert blocks[1][0].source_text == "Value"
