"""Derive a project's current obligation state from one report validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ANALYZED_REPORT_STATUSES = {"awaiting_user_decision", "completed"}


@dataclass(frozen=True, slots=True)
class ObligationProgress:
    state: str
    label: str
    detail: str
    source_anchors: tuple[dict[str, Any], ...]
    pending_review: bool


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def latest_analyzed_report(reports: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the latest report whose validation results can be displayed."""
    analyzed = [
        report for report in reports if str(report.get("status") or "") in ANALYZED_REPORT_STATUSES
    ]
    if not analyzed:
        return None
    return max(
        analyzed,
        key=lambda report: (
            str(report.get("periodEnd") or ""),
            str(report.get("createdAt") or ""),
            str(report.get("id") or ""),
        ),
    )


def obligation_progress(
    validation: dict[str, Any] | None,
) -> ObligationProgress:
    """Collapse API outcomes and human review into four user-facing states."""
    if not validation:
        return ObligationProgress(
            state="unknown",
            label="Necunoscut",
            detail=(
                "Obligația nu are o evaluare în ultimul raport analizat; "
                "starea ei nu poate fi stabilită."
            ),
            source_anchors=(),
            pending_review=False,
        )

    rationale = _clean(validation.get("aiRationale"))
    anchors = tuple(
        anchor for anchor in (validation.get("sourceAnchors") or []) if isinstance(anchor, dict)
    )
    decision = validation.get("userDecision")
    pending_review = not isinstance(decision, dict)
    outcome = _clean(validation.get("aiOutcome"))
    detail = rationale

    if isinstance(decision, dict):
        action = _clean(decision.get("action"))
        comment = _clean(decision.get("comment"))
        if action == "reject":
            return ObligationProgress(
                state="unknown",
                label="Necunoscut",
                detail=comment or "Constatarea AI a fost respinsă de utilizator.",
                source_anchors=(),
                pending_review=False,
            )
        if action == "correct":
            outcome = _clean(decision.get("finalOutcome"))
            detail = comment or rationale

    if outcome == "compliant":
        state, label = "completed", "Finalizată"
    elif outcome == "partially_compliant":
        state, label = "partial", "Progres parțial"
    elif outcome == "non_compliant":
        state, label = "no_progress", "Niciun progres"
    elif outcome == "not_applicable":
        state, label = "unknown", "Neaplicabilă perioadei"
    else:
        state, label = "unknown", "Necunoscut"

    if outcome == "insufficient_evidence":
        detail = (
            "Raportul nu conține suficiente dovezi pentru a stabili progresul. "
            "Absența dovezilor nu înseamnă că obligația nu a fost realizată."
        )

    if not detail:
        detail = {
            "completed": "Raportul indică îndeplinirea obligației.",
            "partial": "Raportul indică realizarea parțială a obligației.",
            "no_progress": "Raportul nu confirmă încă progres pentru această obligație.",
            "unknown": "Raportul nu permite stabilirea stării acestei obligații.",
        }[state]

    return ObligationProgress(
        state=state,
        label=label,
        detail=detail,
        source_anchors=anchors,
        pending_review=pending_review,
    )
