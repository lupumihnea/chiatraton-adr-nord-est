"""Layout-aware, exact-text parsing used only inside the AI adapter.

The parser never performs silent OCR.  SourceAnchor.passage is sliced from the
exact text layer returned here, so the model never gets to invent persisted
quotes.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ParsedPage:
    document_id: UUID
    page_number: int
    text: str


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    document_id: UUID
    pages: tuple[ParsedPage, ...]
    warnings: tuple[str, ...] = ()


def _pdf(document_id: UUID, content: bytes) -> ParsedDocument:
    try:
        import pymupdf
    except ImportError as exc:  # pragma: no cover - depends on optional AI extra
        raise RuntimeError("Install the 'ai' extra: pymupdf is required for PDF parsing") from exc

    pages: list[ParsedPage] = []
    empty: list[int] = []
    with pymupdf.open(stream=content, filetype="pdf") as pdf:
        for page_number, page in enumerate(pdf, start=1):
            text = page.get_text("text") or ""
            if len(text.strip()) < 10:
                empty.append(page_number)
                continue
            pages.append(ParsedPage(document_id, page_number, text))

    warnings: list[str] = []
    if empty:
        preview = ", ".join(map(str, empty[:12])) + ("..." if len(empty) > 12 else "")
        warnings.append(
            f"{len(empty)} PDF page(s) have no extractable text layer: {preview}; "
            "OCR was not performed because evidence must preserve source wording."
        )
    return ParsedDocument(document_id, tuple(pages), tuple(warnings))


def _docx(document_id: UUID, content: bytes) -> ParsedDocument:
    try:
        from docx import Document as DocxDocument
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install the 'ai' extra: python-docx is required for DOCX") from exc

    doc = DocxDocument(io.BytesIO(content))
    blocks: list[str] = []
    pages: list[ParsedPage] = []
    page_number = 1

    def flush() -> None:
        nonlocal blocks, page_number
        text = "\n".join(blocks).strip()
        if text:
            pages.append(ParsedPage(document_id, page_number, text))
            page_number += 1
        blocks = []

    for paragraph in doc.paragraphs:
        text = paragraph.text
        if not text.strip():
            continue
        blocks.append(text)
        if sum(len(item) for item in blocks) >= 5000:
            flush()
    flush()
    return ParsedDocument(document_id, tuple(pages))


def _xlsx(document_id: UUID, content: bytes) -> ParsedDocument:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install the 'ai' extra: openpyxl is required for XLSX") from exc

    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    pages: list[ParsedPage] = []
    page_number = 1
    for sheet in workbook.worksheets:
        rows: list[str] = []
        for row in sheet.iter_rows(values_only=True):
            values = [str(value).strip() for value in row if value is not None and str(value).strip()]
            if values:
                rows.append(" | ".join(values))
            if sum(len(item) for item in rows) >= 4500:
                text = "\n".join(rows).strip()
                if text:
                    pages.append(ParsedPage(document_id, page_number, text))
                    page_number += 1
                rows = []
        if rows:
            pages.append(ParsedPage(document_id, page_number, "\n".join(rows).strip()))
            page_number += 1
    return ParsedDocument(document_id, tuple(pages))


def _xls(document_id: UUID, content: bytes) -> ParsedDocument:
    try:
        import xlrd
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install the 'ai' extra: xlrd is required for legacy XLS") from exc

    workbook = xlrd.open_workbook(file_contents=content)
    pages: list[ParsedPage] = []
    page_number = 1
    for sheet in workbook.sheets():
        rows: list[str] = []
        for row_index in range(sheet.nrows):
            values = [str(value).strip() for value in sheet.row_values(row_index) if str(value).strip()]
            if values:
                rows.append(" | ".join(values))
            if sum(len(item) for item in rows) >= 4500:
                pages.append(ParsedPage(document_id, page_number, "\n".join(rows).strip()))
                page_number += 1
                rows = []
        if rows:
            pages.append(ParsedPage(document_id, page_number, "\n".join(rows).strip()))
            page_number += 1
    return ParsedDocument(document_id, tuple(pages))


def _doc(document_id: UUID, content: bytes) -> ParsedDocument:
    antiword = shutil.which("antiword")
    if not antiword:
        raise RuntimeError("Legacy DOC requires local 'antiword' or conversion to DOCX")
    with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as handle:
        path = Path(handle.name)
        handle.write(content)
    try:
        result = subprocess.run(
            [antiword, str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
    finally:
        path.unlink(missing_ok=True)
    return ParsedDocument(document_id, (ParsedPage(document_id, 1, result.stdout),))


def parse_document_bytes(document_id: UUID, media_type: str, content: bytes) -> ParsedDocument:
    if not content:
        raise RuntimeError("Document content is empty")
    if media_type == "application/pdf":
        return _pdf(document_id, content)
    if media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _docx(document_id, content)
    if media_type == "application/msword":
        return _doc(document_id, content)
    if media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        return _xlsx(document_id, content)
    if media_type == "application/vnd.ms-excel":
        return _xls(document_id, content)
    raise RuntimeError(f"Unsupported AI document media type: {media_type}")
