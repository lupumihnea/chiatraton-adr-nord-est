"""Extract a normalized reporting period from grounded document-QA evidence."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Any

REPORT_PERIOD_QUESTION = (
    "Care este perioada de raportare acoperită de acest raport de progres? "
    "Extrage exact câmpul complet care conține atât data de început, cât și data de sfârșit."
)


class ReportPeriodExtractionError(ValueError):
    """Raised when the report does not ground one unambiguous period."""


_NUMERIC_DATE = re.compile(
    r"(?<!\d)(?:(?P<year>\d{4})[./-](?P<month>\d{1,2})[./-](?P<day>\d{1,2})|"
    r"(?P<day_dmy>\d{1,2})[./-](?P<month_dmy>\d{1,2})[./-](?P<year_dmy>\d{4}))(?!\d)"
)
_TEXT_DATE = re.compile(
    r"(?<!\w)(?P<day>\d{1,2})\s+"
    r"(?P<month>ianuarie|februarie|martie|aprilie|mai|iunie|iulie|august|"
    r"septembrie|octombrie|noiembrie|decembrie)\s+(?P<year>\d{4})(?!\d)",
    re.IGNORECASE,
)
_QUARTER = re.compile(
    r"\btrimestr(?:ul|u)\s+(?P<quarter>i{1,3}|iv|[1-4])"
    r"(?:\s+(?:al|din)\s+anul(?:ui)?)?\s+(?P<year>\d{4})\b",
    re.IGNORECASE,
)
_MONTHS = {
    "ianuarie": 1,
    "februarie": 2,
    "martie": 3,
    "aprilie": 4,
    "mai": 5,
    "iunie": 6,
    "iulie": 7,
    "august": 8,
    "septembrie": 9,
    "octombrie": 10,
    "noiembrie": 11,
    "decembrie": 12,
}
_QUARTERS = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "1": 1, "2": 2, "3": 3, "4": 4}


def _without_diacritics(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )


def _dates_in(text: str) -> list[date]:
    found: list[tuple[int, date]] = []
    for match in _NUMERIC_DATE.finditer(text):
        try:
            if match.group("year"):
                parsed = date(
                    int(match.group("year")),
                    int(match.group("month")),
                    int(match.group("day")),
                )
            else:
                parsed = date(
                    int(match.group("year_dmy")),
                    int(match.group("month_dmy")),
                    int(match.group("day_dmy")),
                )
        except ValueError:
            continue
        found.append((match.start(), parsed))

    normalized = _without_diacritics(text)
    for match in _TEXT_DATE.finditer(normalized):
        try:
            parsed = date(
                int(match.group("year")),
                _MONTHS[match.group("month").casefold()],
                int(match.group("day")),
            )
        except (KeyError, ValueError):
            continue
        found.append((match.start(), parsed))

    return [parsed for _, parsed in sorted(found, key=lambda item: item[0])]


def _quarter_period(texts: list[str]) -> tuple[date, date] | None:
    matches = [match for text in texts for match in _QUARTER.finditer(text)]
    periods: set[tuple[date, date]] = set()
    for match in matches:
        quarter = _QUARTERS[match.group("quarter").casefold()]
        year = int(match.group("year"))
        start_month = (quarter - 1) * 3 + 1
        end_month = start_month + 2
        next_year = year + 1 if end_month == 12 else year
        next_month = date(next_year, (end_month % 12) + 1, 1)
        periods.add((date(year, start_month, 1), date.fromordinal(next_month.toordinal() - 1)))
    if len(periods) == 1:
        return periods.pop()
    return None


def period_from_document_answer(answer: dict[str, Any]) -> tuple[str, str]:
    """Return ISO dates only when the QA response grounds one clear period."""
    if str(answer.get("status") or "") not in {"found", "ambiguous"}:
        raise ReportPeriodExtractionError(
            "Perioada raportată nu a fost găsită explicit în document."
        )

    matches = [item for item in (answer.get("matches") or []) if isinstance(item, dict)]
    values = [str(item["value"]) for item in matches if item.get("value")]
    passages = [
        str(anchor.get("passage") or "")
        for item in matches
        if isinstance((anchor := item.get("sourceAnchor")), dict)
    ]
    dates = [parsed for text in values for parsed in _dates_in(text)]
    unique_dates = set(dates)
    if len(unique_dates) < 2:
        dates.extend(parsed for text in passages for parsed in _dates_in(text))
        unique_dates = set(dates)

    if len(unique_dates) == 2:
        start, end = sorted(unique_dates)
        return start.isoformat(), end.isoformat()
    if len(unique_dates) == 1 and len(dates) >= 2:
        only = unique_dates.pop()
        return only.isoformat(), only.isoformat()

    if not unique_dates:
        quarter = _quarter_period(values + passages)
        if quarter is not None:
            return quarter[0].isoformat(), quarter[1].isoformat()

    if len(unique_dates) > 2:
        raise ReportPeriodExtractionError(
            "Documentul conține mai multe perioade posibile; perioada raportată nu este clară."
        )
    raise ReportPeriodExtractionError(
        "Perioada raportată trebuie să conțină o dată de început și una de sfârșit."
    )
