"""Reusable primitives for evidence-grounded, independently verified claims.

This module is deliberately provider-agnostic. LLM adapters may generate or
verify claims, but the final acceptance rules here are deterministic and do not
perform majority voting.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from uuid import UUID


class AnswerType(StrEnum):
    TEXT = "text"
    BOOLEAN = "boolean"
    DATE = "date"
    NUMBER = "number"
    PERCENTAGE = "percentage"
    CURRENCY = "currency"
    LIST = "list"
    UNKNOWN = "unknown"


class VerificationRole(StrEnum):
    PROVENANCE = "provenance"
    ENTAILMENT = "entailment"
    ADVERSARIAL = "adversarial"
    COMPLETENESS = "completeness"
    NUMERIC = "numeric"


class VerificationVerdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"


class ClaimDecision(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    RETRY = "retry"
    ESCALATE = "escalate"


class VerifiedClaimStatus(StrEnum):
    VERIFIED = "verified"
    REJECTED = "rejected"
    NEEDS_RETRY = "needs_retry"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class AnswerStatus(StrEnum):
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    source_unit_id: str
    document_id: UUID
    page_number: int
    exact_text: str


@dataclass(frozen=True, slots=True)
class GroundedClaim:
    id: str
    statement: str
    evidence: tuple[EvidenceRef, ...]
    answer_type: AnswerType = AnswerType.UNKNOWN
    answer_component: str | None = None


@dataclass(frozen=True, slots=True)
class VerificationResult:
    vendor: str
    model: str
    role: VerificationRole
    verdict: VerificationVerdict
    rationale: str
    contradiction: bool = False
    complete: bool | None = None


@dataclass(frozen=True, slots=True)
class VerifiedClaim:
    claim: GroundedClaim
    verification_results: tuple[VerificationResult, ...]
    status: VerifiedClaimStatus
    decision: ClaimDecision


@dataclass(frozen=True, slots=True)
class Answer:
    claims: tuple[VerifiedClaim, ...]
    status: AnswerStatus


def provenance_verification(
    claim: GroundedClaim,
    page_text: Mapping[tuple[UUID, int], str],
) -> VerificationResult:
    """Check that every cited exact text exists on its declared document page."""
    if not claim.evidence:
        return VerificationResult(
            vendor="local",
            model="deterministic",
            role=VerificationRole.PROVENANCE,
            verdict=VerificationVerdict.FAIL,
            rationale="Claim has no evidence.",
        )

    for evidence in claim.evidence:
        text = page_text.get((evidence.document_id, evidence.page_number), "")
        if not evidence.exact_text.strip() or evidence.exact_text not in text:
            return VerificationResult(
                vendor="local",
                model="deterministic",
                role=VerificationRole.PROVENANCE,
                verdict=VerificationVerdict.FAIL,
                rationale="Evidence text is absent from the declared page.",
            )

    return VerificationResult(
        vendor="local",
        model="deterministic",
        role=VerificationRole.PROVENANCE,
        verdict=VerificationVerdict.PASS,
        rationale="All evidence text was found on the declared pages.",
    )


def compute_numeric_operation(operation: str, operands: Sequence[str | int | Decimal]) -> Decimal:
    """Compute simple numeric answers deterministically from extracted operands."""
    values: list[Decimal] = []
    for operand in operands:
        try:
            values.append(operand if isinstance(operand, Decimal) else Decimal(str(operand)))
        except InvalidOperation as exc:
            raise ValueError("numeric operand is invalid") from exc

    if operation == "add":
        return sum(values, Decimal("0"))
    if operation == "subtract" and len(values) >= 2:
        result = values[0]
        for value in values[1:]:
            result -= value
        return result
    if operation == "multiply":
        result = Decimal("1")
        for value in values:
            result *= value
        return result
    if operation == "divide" and len(values) == 2:
        if values[1] == 0:
            raise ValueError("division by zero")
        return values[0] / values[1]
    raise ValueError("unsupported numeric operation")


def decide_claim(
    claim: GroundedClaim,
    verification_results: Sequence[VerificationResult],
    *,
    require_completeness: bool = True,
) -> VerifiedClaim:
    """Apply deterministic acceptance rules without verifier voting."""
    results = tuple(verification_results)
    by_role: dict[VerificationRole, list[VerificationResult]] = {}
    for result in results:
        by_role.setdefault(result.role, []).append(result)

    provenance = by_role.get(VerificationRole.PROVENANCE, ())
    if not claim.evidence or not provenance:
        return VerifiedClaim(
            claim=claim,
            verification_results=results,
            status=VerifiedClaimStatus.INSUFFICIENT_EVIDENCE,
            decision=ClaimDecision.REJECT,
        )
    if any(result.verdict != VerificationVerdict.PASS for result in provenance):
        return VerifiedClaim(
            claim=claim,
            verification_results=results,
            status=VerifiedClaimStatus.REJECTED,
            decision=ClaimDecision.REJECT,
        )

    entailment = by_role.get(VerificationRole.ENTAILMENT, ())
    if not entailment or any(result.verdict == VerificationVerdict.FAIL for result in entailment):
        return VerifiedClaim(
            claim=claim,
            verification_results=results,
            status=VerifiedClaimStatus.REJECTED,
            decision=ClaimDecision.REJECT,
        )
    if any(
        result.verdict in {VerificationVerdict.PARTIAL, VerificationVerdict.AMBIGUOUS}
        for result in entailment
    ):
        return VerifiedClaim(
            claim=claim,
            verification_results=results,
            status=VerifiedClaimStatus.NEEDS_RETRY,
            decision=ClaimDecision.RETRY,
        )

    adversarial = by_role.get(VerificationRole.ADVERSARIAL, ())
    if any(
        result.contradiction or result.verdict == VerificationVerdict.FAIL
        for result in adversarial
    ):
        return VerifiedClaim(
            claim=claim,
            verification_results=results,
            status=VerifiedClaimStatus.CONFLICTING_EVIDENCE,
            decision=ClaimDecision.ESCALATE,
        )

    completeness = by_role.get(VerificationRole.COMPLETENESS, ())
    if require_completeness and (
        not completeness
        or any(
            result.complete is False
            or result.verdict in {VerificationVerdict.FAIL, VerificationVerdict.PARTIAL}
            for result in completeness
        )
    ):
        return VerifiedClaim(
            claim=claim,
            verification_results=results,
            status=VerifiedClaimStatus.NEEDS_RETRY,
            decision=ClaimDecision.RETRY,
        )

    numeric = by_role.get(VerificationRole.NUMERIC, ())
    if any(result.verdict != VerificationVerdict.PASS for result in numeric):
        return VerifiedClaim(
            claim=claim,
            verification_results=results,
            status=VerifiedClaimStatus.REJECTED,
            decision=ClaimDecision.REJECT,
        )

    return VerifiedClaim(
        claim=claim,
        verification_results=results,
        status=VerifiedClaimStatus.VERIFIED,
        decision=ClaimDecision.ACCEPT,
    )


def assemble_answer(claims: Sequence[VerifiedClaim]) -> Answer:
    """Summarise the verification status for a multi-claim answer."""
    items = tuple(claims)
    if not items:
        return Answer(claims=items, status=AnswerStatus.INSUFFICIENT_EVIDENCE)
    if any(item.status == VerifiedClaimStatus.CONFLICTING_EVIDENCE for item in items):
        return Answer(claims=items, status=AnswerStatus.CONFLICTING_EVIDENCE)
    if all(item.status == VerifiedClaimStatus.VERIFIED for item in items):
        return Answer(claims=items, status=AnswerStatus.VERIFIED)
    if any(item.status == VerifiedClaimStatus.VERIFIED for item in items):
        return Answer(claims=items, status=AnswerStatus.PARTIALLY_VERIFIED)
    return Answer(claims=items, status=AnswerStatus.INSUFFICIENT_EVIDENCE)
