"""Exact source-unit pointers: the LLM returns indexes, never persisted quotes."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceUnit:
    index: int
    start: int
    end: int
    text: str


# Structural pointer boundaries only: this is not obligation-specific logic.
# List bullets are boundaries too, so one paragraph can expose several exact,
# independently groundable spans to the global compiler.
_BOUNDARY = re.compile(
    r"(?:\n{1,}|(?<=[.!?;:])\s+|\s+[•▪◦]\s*|\s+-\s+(?=[A-Za-zĂÂÎȘȚăâîșț]))"
)


def _trim_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def source_units(text: str, *, max_chars: int = 520) -> tuple[SourceUnit, ...]:
    if not text:
        return ()
    spans: list[tuple[int, int]] = []
    cursor = 0
    for match in _BOUNDARY.finditer(text):
        start, end = _trim_span(text, cursor, match.start())
        if end > start:
            spans.append((start, end))
        cursor = match.end()
    start, end = _trim_span(text, cursor, len(text))
    if end > start:
        spans.append((start, end))

    # Split unusually long table lines/paragraphs without changing source chars.
    bounded: list[tuple[int, int]] = []
    for start, end in spans:
        cursor = start
        while end - cursor > max_chars:
            target = cursor + max_chars
            boundary = max(
                text.rfind(" | ", cursor + max_chars // 2, target),
                text.rfind(" ", cursor + max_chars // 2, target),
            )
            cut = boundary if boundary > cursor else target
            piece_start, piece_end = _trim_span(text, cursor, cut)
            if piece_end > piece_start:
                bounded.append((piece_start, piece_end))
            cursor = max(cut, cursor + 1)
        piece_start, piece_end = _trim_span(text, cursor, end)
        if piece_end > piece_start:
            bounded.append((piece_start, piece_end))

    return tuple(
        SourceUnit(index=index, start=start, end=end, text=text[start:end])
        for index, (start, end) in enumerate(bounded)
    )


def exact_slice(text: str, units: tuple[SourceUnit, ...], start: int, end: int) -> str:
    if start < 0 or end < start or end >= len(units):
        raise ValueError("Invalid source-unit range")
    return text[units[start].start : units[end].end]
