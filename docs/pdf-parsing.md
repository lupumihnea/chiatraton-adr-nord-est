# PDF parsing for AI obligation extraction

The AI adapter uses a local, deterministic two-layer parser:

1. **OpenDataLoader PDF** is preferred for structured table extraction. JSON output is used so row/column relationships are preserved; `table_method="cluster"` is enabled for borderless/irregular tables.
2. **PyMuPDF** remains the local text source and fallback. `Page.find_tables()` is used when OpenDataLoader or Java is unavailable.

OpenDataLoader requires Java 11+ on `PATH`. On Windows verify once with:

```powershell
java -version
python -m pip install -e ".[ai]"
```

The default mode is `auto`: try OpenDataLoader, fall back to PyMuPDF without breaking extraction. It can be forced for debugging:

```powershell
$env:CHIATRATON_PDF_TABLE_BACKEND="opendataloader"  # preferred + safe fallback
# or
$env:CHIATRATON_PDF_TABLE_BACKEND="pymupdf"
```

## Why scoring alternatives need a separate parser

MySMIS scoring pages such as `Tip: OPTIUNI` are often visually lists rather than PDF tables. A table parser alone cannot distinguish active and inactive alternatives reliably. ChIAtraton therefore parses these sections deterministically before the LLM:

- only an option explicitly marked `Selectată: Da` may become an AI candidate;
- `Selectată: Nu` alternatives never reach Qwen;
- zero-point selections are ignored;
- application-time financial facts such as solvency/RSG and prior-year turnover ratios are ignored because they are evaluation facts, not future monitoring obligations;
- selected commitments such as employment/maintenance, disadvantaged-worker hiring, own contribution, project location, and concrete environmental measures are retained as candidates.

On option pages the raw flattened PDF text is suppressed for obligation extraction so rejected alternatives cannot re-enter through semantic retrieval.

## Canonical evidence vs semantic table representation

A table row has two deliberately separate representations:

- `StructuredBlock.text` is the semantic representation used by retrieval/Qwen and may
  contain synthetic `Header: value | ...` separators;
- `StructuredBlock.source_text` is a contiguous substring recovered from the original
  PyMuPDF page text and is the only representation allowed to become a persisted
  `SourceAnchor.passage`.

If a table parser cannot mechanically recover an exact canonical substring for a structured
row, that synthetic row is **not** exposed to Qwen. The page remains available through its raw
PyMuPDF text chunks, so recall falls back to the canonical source rather than weakening
provenance. Selected-option pages remain special: their raw flattened page text stays suppressed
to prevent `Selectată: Nu` alternatives from re-entering extraction, while accepted options
carry their exact captured Romanian source text.

## Other guards

- structured table rows are kept atomic and include header-to-cell relationships for semantic retrieval;
- isolated dates/date ranges and tiny orphaned cells are rejected;
- near-duplicate obligations are merged while preserving all distinct `SourceAnchor` references;
- wording persisted as evidence is never translated, rewritten, whitespace-normalized or
  reconstructed by the LLM; the final `SourceAnchor.passage` is exact local Romanian source
  text.
