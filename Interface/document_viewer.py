"""Authenticated document opening with transient, local PDF highlights."""

from __future__ import annotations

import asyncio
import re
import tempfile
import unicodedata
from pathlib import Path
from uuid import uuid4

from nicegui import app, ui

from Interface.api_client import api_client, api_error_message


def _token(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[^\w%]+", "", normalized, flags=re.UNICODE)


def _word_rectangles(page: object, passage: str) -> list[object]:
    import fitz

    words = page.get_text("words", sort=True)  # type: ignore[attr-defined]
    indexed_words = [(word, _token(str(word[4]))) for word in words]
    indexed_words = [(word, token) for word, token in indexed_words if token]
    needle = [_token(part) for part in passage.split()]
    needle = [part for part in needle if part]
    if not needle:
        return []

    match: list[tuple[object, ...]] = []
    for start in range(len(indexed_words)):
        if indexed_words[start][1] != needle[0]:
            continue
        candidate = indexed_words[start : start + len(needle)]
        if [item[1] for item in candidate] == needle:
            match = [item[0] for item in candidate]
            break
    if not match:
        return []

    rectangles: list[object] = []
    current_key: tuple[int, int] | None = None
    current_rect: object | None = None
    for word in match:
        key = (int(word[5]), int(word[6]))
        rect = fitz.Rect(word[:4])
        if key == current_key and current_rect is not None:
            current_rect |= rect
        else:
            if current_rect is not None:
                rectangles.append(current_rect)
            current_key = key
            current_rect = rect
    if current_rect is not None:
        rectangles.append(current_rect)
    return rectangles


def _highlight_pdf(content: bytes, page_number: int, passage: str) -> tuple[bytes, bool]:
    import fitz

    highlighted = False
    with fitz.open(stream=content, filetype="pdf") as document:
        if 1 <= page_number <= document.page_count and passage.strip():
            page = document[page_number - 1]
            quads = page.search_for(passage.strip(), quads=True)
            if quads:
                page.add_highlight_annot(quads)
                highlighted = True
            else:
                rectangles = _word_rectangles(page, passage)
                if rectangles:
                    page.add_highlight_annot(rectangles)
                    highlighted = True
                else:
                    # Long wrapped passages can defeat exact phrase search. A few
                    # distinctive source lines still give the user a reliable locator.
                    snippets = [
                        line.strip()
                        for line in passage.splitlines()
                        if len(line.strip()) >= 12
                    ][:4]
                    for snippet in snippets:
                        found = page.search_for(snippet, quads=True)
                        if found:
                            page.add_highlight_annot(found)
                            highlighted = True
        return document.tobytes(garbage=4, deflate=True), highlighted


async def _delete_later(path: Path, url_path: str) -> None:
    await asyncio.sleep(600)
    app.remove_route(url_path)
    path.unlink(missing_ok=True)


async def open_document_at_anchor(
    document_id: str,
    fallback_name: str,
    *,
    page_number: int | None = None,
    passage: str | None = None,
) -> None:
    try:
        content, filename = await api_client.get_document_content(document_id)
    except Exception as error:
        ui.notify(api_error_message(error), type="negative", timeout=8000)
        return

    resolved_name = filename or fallback_name
    is_pdf = content.startswith(b"%PDF") or resolved_name.lower().endswith(".pdf")
    if not is_pdf:
        ui.download(content, filename=resolved_name)
        return

    output = content
    highlighted = False
    if page_number is not None and passage:
        try:
            output, highlighted = await asyncio.to_thread(
                _highlight_pdf, content, page_number, passage
            )
        except Exception:
            output = content

    handle = tempfile.NamedTemporaryFile(prefix="chiatraton-", suffix=".pdf", delete=False)
    path = Path(handle.name)
    try:
        handle.write(output)
    finally:
        handle.close()
    url_path = f"/_chiatraton/document-preview/{uuid4()}.pdf"
    url = app.add_media_file(local_file=path, url_path=url_path)
    target = f"{url}#page={page_number}" if page_number is not None else url
    ui.navigate.to(target, new_tab=True)
    asyncio.create_task(_delete_later(path, url_path))
    if passage and not highlighted:
        ui.notify(
            "Documentul a fost deschis la pagină; pasajul nu a putut fi evidențiat exact.",
            type="warning",
        )
