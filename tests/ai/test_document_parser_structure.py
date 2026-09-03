from uuid import uuid4

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


def test_selected_options_drop_unselected_and_historical_financial_facts() -> None:
    pages = [
        """
Descriere subcriteriu:
1.3 Cresterea numarului mediu de salariati ca urmare a realizarii investitiei
Tip: OPTIUNI
Descriere:
a. Investiția prevede creșterea numărului mediu de salariați cu mai mult de 2 și menținerea acestei creșteri pe perioada de monitorizare
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
3.1 Rata solvabilităţii generale a microîntreprinderii pe anul fiscal anterior depunerii cererii de finantare
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
    assert 2 not in blocks  # selected RSG is historical, not an obligation


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
