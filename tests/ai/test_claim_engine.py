from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from AI.claim_engine import (
    AnswerStatus,
    AnswerType,
    ClaimDecision,
    EvidenceRef,
    GroundedClaim,
    VerificationResult,
    VerificationRole,
    VerificationVerdict,
    VerifiedClaimStatus,
    assemble_answer,
    compute_numeric_operation,
    decide_claim,
    provenance_verification,
)


def _claim() -> GroundedClaim:
    document_id = uuid4()
    return GroundedClaim(
        id="C1",
        statement="Contribuția solicitantului este 20%.",
        answer_type=AnswerType.PERCENTAGE,
        answer_component="20%",
        evidence=(
            EvidenceRef(
                source_unit_id="doc:p1:u1",
                document_id=document_id,
                page_number=1,
                exact_text="Contribuția solicitantului 20%",
            ),
        ),
    )


def _result(
    role: VerificationRole,
    verdict: VerificationVerdict = VerificationVerdict.PASS,
    *,
    contradiction: bool = False,
    complete: bool | None = None,
) -> VerificationResult:
    return VerificationResult(
        vendor="test-vendor",
        model="test-model",
        role=role,
        verdict=verdict,
        rationale="synthetic verifier result",
        contradiction=contradiction,
        complete=complete,
    )


def test_provenance_verification_requires_exact_page_text() -> None:
    claim = _claim()
    page_text = {
        (claim.evidence[0].document_id, 1): (
            "Text înainte. Contribuția solicitantului 20%. Text după."
        )
    }

    assert provenance_verification(claim, page_text).verdict == VerificationVerdict.PASS
    assert provenance_verification(claim, {}).verdict == VerificationVerdict.FAIL


def test_decide_claim_accepts_only_when_all_required_properties_pass() -> None:
    claim = _claim()
    verified = decide_claim(
        claim,
        (
            _result(VerificationRole.PROVENANCE),
            _result(VerificationRole.ENTAILMENT),
            _result(VerificationRole.ADVERSARIAL),
            _result(VerificationRole.COMPLETENESS, complete=True),
        ),
    )

    assert verified.decision == ClaimDecision.ACCEPT
    assert verified.status == VerifiedClaimStatus.VERIFIED


def test_decide_claim_does_not_vote_over_verifier_failures() -> None:
    claim = _claim()
    rejected = decide_claim(
        claim,
        (
            _result(VerificationRole.PROVENANCE),
            _result(VerificationRole.ENTAILMENT, VerificationVerdict.FAIL),
            _result(VerificationRole.ADVERSARIAL),
            _result(VerificationRole.COMPLETENESS, complete=True),
        ),
    )

    assert rejected.decision == ClaimDecision.REJECT
    assert rejected.status == VerifiedClaimStatus.REJECTED


def test_decide_claim_escalates_contradictions_and_retries_incomplete_answers() -> None:
    claim = _claim()
    conflicting = decide_claim(
        claim,
        (
            _result(VerificationRole.PROVENANCE),
            _result(VerificationRole.ENTAILMENT),
            _result(VerificationRole.ADVERSARIAL, contradiction=True),
            _result(VerificationRole.COMPLETENESS, complete=True),
        ),
    )
    incomplete = decide_claim(
        claim,
        (
            _result(VerificationRole.PROVENANCE),
            _result(VerificationRole.ENTAILMENT),
            _result(VerificationRole.ADVERSARIAL),
            _result(VerificationRole.COMPLETENESS, complete=False),
        ),
    )

    assert conflicting.decision == ClaimDecision.ESCALATE
    assert conflicting.status == VerifiedClaimStatus.CONFLICTING_EVIDENCE
    assert incomplete.decision == ClaimDecision.RETRY
    assert incomplete.status == VerifiedClaimStatus.NEEDS_RETRY


def test_numeric_operations_are_deterministic() -> None:
    assert compute_numeric_operation("subtract", ["9", "6"]) == Decimal("3")
    assert compute_numeric_operation("add", ["1.5", "2.5"]) == Decimal("4.0")

    with pytest.raises(ValueError, match="division by zero"):
        compute_numeric_operation("divide", ["9", "0"])


def test_assemble_answer_summarizes_claim_statuses() -> None:
    claim = _claim()
    verified = decide_claim(
        claim,
        (
            _result(VerificationRole.PROVENANCE),
            _result(VerificationRole.ENTAILMENT),
            _result(VerificationRole.COMPLETENESS, complete=True),
        ),
    )
    retry = decide_claim(
        claim,
        (
            _result(VerificationRole.PROVENANCE),
            _result(VerificationRole.ENTAILMENT),
            _result(VerificationRole.COMPLETENESS, complete=False),
        ),
    )

    assert assemble_answer((verified,)).status == AnswerStatus.VERIFIED
    assert assemble_answer((verified, retry)).status == AnswerStatus.PARTIALLY_VERIFIED
    assert assemble_answer(()).status == AnswerStatus.INSUFFICIENT_EVIDENCE
