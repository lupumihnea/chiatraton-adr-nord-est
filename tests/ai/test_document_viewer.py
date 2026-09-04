import fitz

from Interface.document_viewer import _highlight_pdf


def test_highlight_pdf_marks_the_requested_page() -> None:
    document = fitz.open()
    document.new_page().insert_text((72, 72), "Prima pagina")
    document.new_page().insert_text((72, 72), "Contributia proprie este 20 la suta")
    content = document.tobytes()
    document.close()

    result, highlighted = _highlight_pdf(
        content,
        2,
        "Contributia proprie este 20 la suta",
    )

    assert highlighted is True
    with fitz.open(stream=result, filetype="pdf") as marked:
        assert marked[0].first_annot is None
        assert marked[1].first_annot is not None
