from pathlib import Path

import pytest

from Interface.obligation_progress import latest_analyzed_report, obligation_progress


def test_latest_analyzed_report_uses_latest_period_and_ignores_unanalyzed() -> None:
    reports = [
        {
            "id": "older",
            "status": "completed",
            "periodEnd": "2025-03-31",
            "createdAt": "2025-04-02T10:00:00Z",
        },
        {
            "id": "newer-unready",
            "status": "analysis_in_progress",
            "periodEnd": "2025-09-30",
            "createdAt": "2025-10-02T10:00:00Z",
        },
        {
            "id": "latest-analyzed",
            "status": "awaiting_user_decision",
            "periodEnd": "2025-06-30",
            "createdAt": "2025-07-02T10:00:00Z",
        },
    ]

    assert latest_analyzed_report(reports)["id"] == "latest-analyzed"  # type: ignore[index]


@pytest.mark.parametrize(
    ("outcome", "expected_state", "expected_label"),
    [
        ("non_compliant", "no_progress", "Niciun progres"),
        ("insufficient_evidence", "no_progress", "Niciun progres"),
        ("partially_compliant", "partial", "Progres parțial"),
        ("compliant", "completed", "Finalizată"),
    ],
)
def test_ai_outcomes_map_to_three_progress_states(
    outcome: str, expected_state: str, expected_label: str
) -> None:
    progress = obligation_progress(
        {
            "aiOutcome": outcome,
            "aiRationale": "Au fost realizate activitățile documentate.",
            "sourceAnchors": [{"documentId": "doc-1", "pageNumber": 4}],
            "userDecision": None,
        }
    )

    assert progress.state == expected_state
    assert progress.label == expected_label
    assert progress.pending_review is True
    assert progress.source_anchors[0]["documentId"] == "doc-1"


def test_human_correction_overrides_ai_outcome_and_explains_progress() -> None:
    progress = obligation_progress(
        {
            "aiOutcome": "non_compliant",
            "aiRationale": "Evaluare inițială.",
            "sourceAnchors": [],
            "userDecision": {
                "action": "correct",
                "finalOutcome": "partially_compliant",
                "comment": "Două dintre cele trei echipamente au fost recepționate.",
            },
        }
    )

    assert progress.state == "partial"
    assert progress.detail == "Două dintre cele trei echipamente au fost recepționate."
    assert progress.pending_review is False


def test_rejected_ai_finding_does_not_become_confirmed_progress() -> None:
    progress = obligation_progress(
        {
            "aiOutcome": "compliant",
            "aiRationale": "Evaluare eronată.",
            "sourceAnchors": [{"documentId": "doc-1", "pageNumber": 2}],
            "userDecision": {
                "action": "reject",
                "comment": "Pasajul se referă la altă activitate.",
            },
        }
    )

    assert progress.state == "no_progress"
    assert progress.detail == "Pasajul se referă la altă activitate."
    assert progress.source_anchors == ()


def test_project_page_loads_latest_progress_and_links_report_evidence() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "Interface" / "project_details.py").read_text(encoding="utf-8")

    assert "latest_analyzed_report(reports)" in source
    assert "list_all_report_validations" in source
    assert '"Dovadă progres {index} · pagina "' in source
    assert "open_document_at_anchor" in source
