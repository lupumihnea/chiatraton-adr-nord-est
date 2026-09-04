import pytest

from Interface.report_period import ReportPeriodExtractionError, period_from_document_answer


def _answer(*, value: str | None, passage: str, status: str = "found") -> dict:
    return {
        "status": status,
        "matches": [
            {
                "value": value,
                "sourceAnchor": {
                    "documentId": "document-1",
                    "pageNumber": 1,
                    "passage": passage,
                },
            }
        ],
    }


def test_extracts_numeric_period_from_grounded_value() -> None:
    answer = _answer(
        value="01.01.2025 - 30.06.2025",
        passage="Perioada de raportare: 01.01.2025 - 30.06.2025.",
    )

    assert period_from_document_answer(answer) == ("2025-01-01", "2025-06-30")


def test_extracts_textual_dates_from_grounded_passage() -> None:
    answer = _answer(
        value=None,
        passage="Raport aferent perioadei 1 ianuarie 2025 - 31 martie 2025.",
    )

    assert period_from_document_answer(answer) == ("2025-01-01", "2025-03-31")


def test_extracts_quarter_when_report_uses_quarter_notation() -> None:
    answer = _answer(
        value="Trimestrul II 2025",
        passage="Perioada raportată: Trimestrul II 2025.",
    )

    assert period_from_document_answer(answer) == ("2025-04-01", "2025-06-30")


@pytest.mark.parametrize(
    "answer",
    [
        {"status": "not_found", "matches": []},
        _answer(
            value="01.01.2025 - 31.03.2025 și 30.06.2025",
            passage="Sunt menționate mai multe perioade.",
            status="ambiguous",
        ),
    ],
)
def test_rejects_missing_or_ambiguous_period(answer: dict) -> None:
    with pytest.raises(ReportPeriodExtractionError):
        period_from_document_answer(answer)
