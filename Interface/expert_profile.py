"""Deterministic confidence and expert-profile helpers for the demo UI.

The values in this module are deliberately explainable heuristics. They are not
model probabilities and they never change the API decision or source evidence.
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

_FALSE_VALUES = {"0", "false", "no", "off"}
_WORD_RE = re.compile(r"[a-z0-9]+")
_STOP_WORDS = {
    "a",
    "ai",
    "ale",
    "al",
    "ca",
    "care",
    "cu",
    "de",
    "din",
    "este",
    "fi",
    "in",
    "la",
    "o",
    "pentru",
    "pe",
    "prin",
    "sa",
    "se",
    "si",
    "sunt",
    "un",
    "unei",
}


@dataclass(frozen=True, slots=True)
class ExpertProfile:
    """Page-local, auditable summary of demonstrated review preferences."""

    accepted: int
    corrected: int
    rejected: int
    evidence_preference: float
    exact_wording_preference: float
    explicit_deadline_preference: float
    last_learning: str

    @property
    def decisions(self) -> int:
        return self.accepted + self.corrected + self.rejected

    @property
    def adaptation_percent(self) -> int:
        return min(96, 52 + self.decisions * 2)

    @property
    def traits(self) -> tuple[str, ...]:
        traits = ["Dovada are prioritate"]
        if self.exact_wording_preference >= 0.7:
            traits.append("Preferă formulări apropiate de sursă")
        if self.explicit_deadline_preference >= 0.7:
            traits.append("Verifică termenele explicite")
        return tuple(traits)


@dataclass(frozen=True, slots=True)
class ConfidenceFactor:
    label: str
    score: int


@dataclass(frozen=True, slots=True)
class ConfidenceAssessment:
    """Explainable UI assessment; ``overall`` is not a probability."""

    overall: int
    level: str
    color: str
    recommendation: str
    factors: tuple[ConfidenceFactor, ...]
    attention: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProfileUpdate:
    profile: ExpertProfile
    message: str


def expert_profile_demo_enabled(environ: dict[str, str] | None = None) -> bool:
    """Enable the demo in non-production unless an explicit flag says otherwise."""

    values = os.environ if environ is None else environ
    explicit = values.get("CHIATRATON_DEMO_EXPERT_PROFILE")
    if explicit is not None:
        return explicit.strip().lower() not in _FALSE_VALUES
    return values.get("CHIATRATON_ENVIRONMENT", "development").strip().lower() != "production"


def demonstration_profile() -> ExpertProfile:
    """Return a stable pre-calibrated profile for a compelling local demo."""

    return ExpertProfile(
        accepted=7,
        corrected=4,
        rejected=1,
        evidence_preference=0.9,
        exact_wording_preference=0.82,
        explicit_deadline_preference=0.78,
        last_learning="Termenele implicite sunt trimise prioritar către verificare.",
    )


def assess_proposal(
    proposal: dict[str, Any],
    profile: ExpertProfile,
) -> ConfidenceAssessment:
    """Build a deterministic, bounded and explainable assessment for a proposal."""

    description = _clean(proposal.get("proposedDescription"))
    code = _clean(proposal.get("proposedCode"))
    deadline = _clean(proposal.get("proposedDeadline"))
    anchors = [item for item in proposal.get("sourceAnchors") or [] if isinstance(item, dict)]
    passages = [_clean(item.get("passage")) for item in anchors]
    passages = [passage for passage in passages if passage]
    combined_passage = " ".join(passages)
    overlap = _lexical_overlap(description, combined_passage)
    has_page = bool(anchors) and all(_valid_page(item.get("pageNumber")) for item in anchors)
    longest_passage = max((len(item) for item in passages), default=0)
    deadline_is_explicit = bool(deadline) and _deadline_appears(deadline, combined_passage)

    if not passages:
        evidence_score = 18
    else:
        evidence_score = 57
        evidence_score += 8 if has_page else 0
        evidence_score += min(18, round(longest_passage / 18))
        evidence_score += round(15 * overlap)
    evidence_score = _bounded(evidence_score)

    word_count = len(_tokens(description))
    clarity_score = 43
    if code:
        clarity_score += 9
    if 8 <= word_count <= 70:
        clarity_score += 25
    elif word_count:
        clarity_score += 14
    if deadline:
        clarity_score += 9 if deadline_is_explicit else 2
    else:
        clarity_score += 6
    if description.endswith((".", ";")):
        clarity_score += 3
    clarity_score = _bounded(clarity_score)

    profile_score = 60
    profile_score += round(24 * overlap * profile.exact_wording_preference)
    profile_score += round(8 * (evidence_score / 100) * profile.evidence_preference)
    if deadline:
        if deadline_is_explicit:
            profile_score += round(9 * profile.explicit_deadline_preference)
        else:
            profile_score -= round(18 * profile.explicit_deadline_preference)
    else:
        profile_score += round(4 * profile.explicit_deadline_preference)
    profile_score = _bounded(profile_score)

    overall = _bounded(round(0.5 * evidence_score + 0.3 * clarity_score + 0.2 * profile_score))
    level, color, recommendation = _confidence_presentation(overall)

    attention: list[str] = []
    if not passages:
        attention.append("Dovada sursă lipsește.")
    elif longest_passage < 60:
        attention.append("Pasajul este scurt; verifică contextul din document.")
    if passages and overlap < 0.2:
        attention.append("Compară atent formularea propusă cu pasajul sursă.")
    if deadline and not deadline_is_explicit:
        attention.append("Termenul necesită confirmare explicită în pasaj.")

    return ConfidenceAssessment(
        overall=overall,
        level=level,
        color=color,
        recommendation=recommendation,
        factors=(
            ConfidenceFactor("Dovadă în document", evidence_score),
            ConfidenceFactor("Claritatea extracției", clarity_score),
            ConfidenceFactor("Potrivire cu profilul", profile_score),
        ),
        attention=tuple(attention[:3]),
    )


def learn_from_review(
    profile: ExpertProfile,
    *,
    action: str,
    proposal: dict[str, Any],
    correction: dict[str, Any] | None = None,
    rejection_reason: str | None = None,
) -> ProfileUpdate:
    """Return a new page-local profile after a successfully persisted review."""

    if action == "accept":
        updated = replace(
            profile,
            accepted=profile.accepted + 1,
            evidence_preference=min(1.0, profile.evidence_preference + 0.005),
            last_learning="Structura acestei obligații a fost confirmată de expert.",
        )
    elif action == "correct":
        correction = correction or {}
        old_description = _clean(proposal.get("proposedDescription"))
        new_description = _clean(correction.get("description"))
        old_deadline = _clean(proposal.get("proposedDeadline"))
        new_deadline = _clean(correction.get("deadline"))
        description_changed = bool(new_description and new_description != old_description)
        deadline_changed = old_deadline != new_deadline

        if deadline_changed:
            learning = (
                "Preferința expertului a fost înregistrată: termenele trebuie "
                "susținute explicit de sursă."
            )
        elif description_changed:
            learning = (
                "Preferința expertului a fost înregistrată: formulările apropiate "
                "de sursă vor fi prioritizate."
            )
        else:
            learning = "Corecția a fost înregistrată pentru evaluările viitoare."

        updated = replace(
            profile,
            corrected=profile.corrected + 1,
            exact_wording_preference=min(
                1.0,
                profile.exact_wording_preference + (0.025 if description_changed else 0.005),
            ),
            explicit_deadline_preference=min(
                1.0,
                profile.explicit_deadline_preference + (0.04 if deadline_changed else 0.005),
            ),
            last_learning=learning,
        )
    elif action == "reject":
        reason_messages = {
            "insufficient_evidence": "Pragul pentru calitatea dovezii a fost consolidat.",
            "not_obligation": "Formulările fără caracter obligatoriu vor primi atenție sporită.",
            "duplicate": "Propunerile potențial duplicate vor fi semnalate mai devreme.",
            "too_general": "Formulările prea generale vor fi trimise către verificare.",
        }
        learning = reason_messages.get(
            rejection_reason or "",
            "Motivul respingerii a fost înregistrat pentru evaluările viitoare.",
        )
        updated = replace(
            profile,
            rejected=profile.rejected + 1,
            evidence_preference=min(1.0, profile.evidence_preference + 0.03),
            last_learning=learning,
        )
    else:
        raise ValueError(f"Unsupported review action: {action}")

    return ProfileUpdate(profile=updated, message=updated.last_learning)


def profile_from_proposals(
    proposals: list[dict[str, Any]],
    *,
    baseline: ExpertProfile | None = None,
) -> ExpertProfile:
    """Rebuild the page profile from persisted reviews, making reloads deterministic."""

    profile = baseline or demonstration_profile()
    ordered = sorted(proposals, key=_review_order)
    for proposal in ordered:
        review = proposal.get("review")
        if not isinstance(review, dict):
            continue
        action = str(review.get("action") or "")
        if action not in {"accept", "correct", "reject"}:
            continue
        profile = learn_from_review(
            profile,
            action=action,
            proposal=proposal,
            correction=(
                review.get("correction") if isinstance(review.get("correction"), dict) else None
            ),
            rejection_reason=_rejection_reason_from_comment(review.get("comment")),
        ).profile
    return profile


def _clean(value: object) -> str:
    return " ".join(str(value or "").split())


def _review_order(proposal: dict[str, Any]) -> tuple[str, str]:
    review = proposal.get("review")
    reviewed_at = _clean(review.get("reviewedAt")) if isinstance(review, dict) else ""
    return reviewed_at, _clean(proposal.get("id"))


def _rejection_reason_from_comment(value: object) -> str | None:
    comment = _clean(value).lower()
    labels = {
        "nu este o obligație": "not_obligation",
        "dovadă insuficientă": "insufficient_evidence",
        "propunere duplicată": "duplicate",
        "formulare prea generală": "too_general",
    }
    return next((code for label, code in labels.items() if comment.startswith(label)), None)


def _tokens(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", value.lower())
    without_marks = "".join(char for char in normalized if not unicodedata.combining(char))
    return {
        token
        for token in _WORD_RE.findall(without_marks)
        if len(token) >= 3 and token not in _STOP_WORDS
    }


def _lexical_overlap(description: str, passage: str) -> float:
    description_tokens = _tokens(description)
    if not description_tokens:
        return 0.0
    return len(description_tokens & _tokens(passage)) / len(description_tokens)


def _valid_page(value: object) -> bool:
    try:
        return int(value) >= 1
    except (TypeError, ValueError):
        return False


def _deadline_appears(raw_deadline: str, passage: str) -> bool:
    candidates = {raw_deadline}
    try:
        parsed = date.fromisoformat(raw_deadline)
        candidates.update(
            {
                parsed.strftime("%d.%m.%Y"),
                parsed.strftime("%d/%m/%Y"),
                parsed.strftime("%d-%m-%Y"),
            }
        )
    except ValueError:
        pass
    normalized_passage = passage.lower()
    return any(candidate.lower() in normalized_passage for candidate in candidates)


def _bounded(value: int) -> int:
    return max(0, min(100, value))


def _confidence_presentation(score: int) -> tuple[str, str, str]:
    if score >= 85:
        return "Ridicată", "positive", "Poate fi verificată rapid"
    if score >= 65:
        return "Medie", "warning", "Verificare recomandată"
    return "Scăzută", "negative", "Necesită atenția expertului"
