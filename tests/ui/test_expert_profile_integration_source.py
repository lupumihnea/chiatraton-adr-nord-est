from pathlib import Path


def test_criteria_review_exposes_confidence_without_the_large_profile_panel() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "Interface" / "criteria_review.py").read_text(encoding="utf-8")
    profile_source = (root / "Interface" / "expert_profile.py").read_text(encoding="utf-8")

    assert "Profil expert adaptiv" not in source
    assert "PREVIZUALIZARE DEMO" not in source
    assert "Încredere estimată" in source
    assert "Cum a fost estimat scorul" in source
    assert "Dovadă în document" in profile_source
    assert "Claritatea extracției" in profile_source
    assert "Potrivire cu profilul" in profile_source
    assert "probabilitate calibrată" in source


def test_profile_learns_only_after_successful_api_review() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "Interface" / "criteria_review.py").read_text(encoding="utf-8")
    review_one = source.index("async def review_one(")
    api_success = source.index("await api_client.review_criterion_proposals(", review_one)
    learning = source.index("update = learn_from_review(", api_success)
    refresh = source.index("await proposals_view.refresh()", learning)

    assert review_one < api_success < learning < refresh


def test_review_heading_is_centered_and_intro_copy_is_removed() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "Interface" / "criteria_review.py").read_text(encoding="utf-8")

    assert "absolute left-1/2 -translate-x-1/2" in source
    assert "AI-ul propune obligațiile, dar acestea devin obligații confirmate" not in source
