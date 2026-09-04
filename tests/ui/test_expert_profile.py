from __future__ import annotations

import pytest

from Interface.expert_profile import (
    ExpertProfile,
    assess_proposal,
    demonstration_profile,
    expert_profile_demo_enabled,
    learn_from_review,
    profile_from_proposals,
)


def _proposal(*, passage: str, deadline: str | None = "2027-03-31") -> dict[str, object]:
    return {
        "id": "proposal-1",
        "revision": 1,
        "proposedCode": "OBL-01",
        "proposedDescription": ("Beneficiarul transmite raportul trimestrial până la 31.03.2027."),
        "proposedDeadline": deadline,
        "sourceAnchors": [
            {
                "documentId": "document-1",
                "pageNumber": 2,
                "passage": passage,
            }
        ],
    }


def test_demonstration_profile_has_stable_baseline() -> None:
    profile = demonstration_profile()

    assert profile.decisions == 12
    assert profile.adaptation_percent == 76
    assert profile.traits == (
        "Dovada are prioritate",
        "Preferă formulări apropiate de sursă",
        "Verifică termenele explicite",
    )


def test_assessment_is_deterministic_and_bounded() -> None:
    profile = demonstration_profile()
    proposal = _proposal(
        passage=(
            "Beneficiarul transmite raportul trimestrial către ADR Nord-Est până la "
            "31.03.2027, în formatul prevăzut de contract și cu anexele justificative."
        )
    )

    first = assess_proposal(proposal, profile)
    second = assess_proposal(proposal, profile)

    assert first == second
    assert 0 <= first.overall <= 100
    assert all(0 <= factor.score <= 100 for factor in first.factors)
    assert first.level == "Ridicată"


def test_grounded_passage_scores_above_weak_anchor() -> None:
    profile = demonstration_profile()
    grounded = _proposal(
        passage=(
            "Beneficiarul transmite raportul trimestrial către ADR Nord-Est până la "
            "31.03.2027, împreună cu toate anexele justificative solicitate."
        )
    )
    weak = _proposal(passage="Raport general.")

    grounded_assessment = assess_proposal(grounded, profile)
    weak_assessment = assess_proposal(weak, profile)

    assert grounded_assessment.overall > weak_assessment.overall
    assert grounded_assessment.factors[0].score > weak_assessment.factors[0].score
    assert weak_assessment.attention


def test_missing_anchor_is_low_confidence_and_explained() -> None:
    proposal = _proposal(passage="Text")
    proposal["sourceAnchors"] = []

    assessment = assess_proposal(proposal, demonstration_profile())

    assert assessment.overall < 65
    assert assessment.level == "Scăzută"
    assert "Dovada sursă lipsește." in assessment.attention


def test_explicit_deadline_improves_assessment() -> None:
    explicit = _proposal(
        passage=(
            "Beneficiarul transmite raportul trimestrial până la 31.03.2027, "
            "împreună cu anexele justificative."
        )
    )
    inferred = _proposal(
        passage=(
            "Beneficiarul transmite raportul trimestrial împreună cu anexele "
            "justificative solicitate de autoritate."
        )
    )

    explicit_score = assess_proposal(explicit, demonstration_profile())
    inferred_score = assess_proposal(inferred, demonstration_profile())

    assert explicit_score.overall > inferred_score.overall
    assert "Termenul necesită confirmare explicită în pasaj." in inferred_score.attention


def test_learning_returns_new_profile_only_after_review_is_applied() -> None:
    profile = demonstration_profile()
    proposal = _proposal(passage="Beneficiarul transmite raportul trimestrial.")

    update = learn_from_review(profile, action="accept", proposal=proposal)

    assert update.profile is not profile
    assert profile.decisions == 12
    assert update.profile.decisions == 13
    assert update.profile.accepted == profile.accepted + 1


def test_deadline_correction_teaches_explicit_deadline_preference() -> None:
    profile = demonstration_profile()
    proposal = _proposal(passage="Beneficiarul transmite raportul trimestrial.")
    correction = {
        "description": proposal["proposedDescription"],
        "deadline": None,
    }

    update = learn_from_review(
        profile,
        action="correct",
        proposal=proposal,
        correction=correction,
    )

    assert update.profile.corrected == profile.corrected + 1
    assert update.profile.explicit_deadline_preference > profile.explicit_deadline_preference
    assert "termenele trebuie susținute explicit" in update.message


@pytest.mark.parametrize(
    ("reason", "message_fragment"),
    [
        ("insufficient_evidence", "calitatea dovezii"),
        ("not_obligation", "fără caracter obligatoriu"),
        ("duplicate", "duplicate"),
        ("too_general", "prea generale"),
    ],
)
def test_rejection_reason_produces_explainable_learning(
    reason: str,
    message_fragment: str,
) -> None:
    profile = demonstration_profile()

    update = learn_from_review(
        profile,
        action="reject",
        proposal=_proposal(passage="Textul sursă al obligației."),
        rejection_reason=reason,
    )

    assert update.profile.rejected == profile.rejected + 1
    assert message_fragment in update.message


def test_demo_flag_is_off_by_default_in_production_and_explicitly_overridable() -> None:
    assert not expert_profile_demo_enabled({"CHIATRATON_ENVIRONMENT": "production"})
    assert expert_profile_demo_enabled(
        {
            "CHIATRATON_ENVIRONMENT": "production",
            "CHIATRATON_DEMO_EXPERT_PROFILE": "true",
        }
    )
    assert not expert_profile_demo_enabled(
        {
            "CHIATRATON_ENVIRONMENT": "development",
            "CHIATRATON_DEMO_EXPERT_PROFILE": "off",
        }
    )


def test_profiles_are_independent() -> None:
    first = demonstration_profile()
    second = demonstration_profile()

    changed = learn_from_review(
        first,
        action="reject",
        proposal=_proposal(passage="Textul sursă."),
        rejection_reason="too_general",
    ).profile

    assert changed.decisions == first.decisions + 1
    assert second == demonstration_profile()
    assert isinstance(second, ExpertProfile)


def test_profile_is_rebuilt_from_persisted_reviews_after_reload() -> None:
    accepted = _proposal(passage="Textul sursă al obligației.")
    accepted["id"] = "accepted"
    accepted["review"] = {"action": "accept", "correction": None, "comment": None}
    rejected = _proposal(passage="Un pasaj fără suport suficient.")
    rejected["id"] = "rejected"
    rejected["review"] = {
        "action": "reject",
        "correction": None,
        "comment": "Dovadă insuficientă: pasaj prea general",
    }

    profile = profile_from_proposals([rejected, accepted])
    same_profile = profile_from_proposals([accepted, rejected])

    assert profile == same_profile
    assert profile.decisions == 14
    assert profile.accepted == 8
    assert profile.rejected == 2
    assert profile.last_learning == "Pragul pentru calitatea dovezii a fost consolidat."
