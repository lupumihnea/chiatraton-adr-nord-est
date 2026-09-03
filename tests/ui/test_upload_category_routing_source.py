from pathlib import Path


def test_upload_requires_explicit_category_and_keeps_selector_editable() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "Interface" / "upload_documents.py").read_text(encoding="utf-8")

    assert '"category": None' in source
    assert 'value=None' in source
    assert 'label="Alege categoria documentului"' in source
    assert 'category_select.disable()' not in source
    assert 'if category is None:' in source
    assert 'Alege categoria pentru' in source
    assert 'OBLIGATION_SOURCE_CATEGORIES = {"apel", "initiale"}' in source
    assert 'PROGRESS_REPORT_CATEGORY = "rapoarte"' in source
