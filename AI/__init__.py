"""Qwen/OpenRouter adapter for the ChIAtraton AIClient ports."""

from AI.claim_engine import (
    Answer,
    AnswerStatus,
    AnswerType,
    ClaimDecision,
    EvidenceRef,
    GroundedClaim,
    VerificationResult,
    VerificationRole,
    VerificationVerdict,
    VerifiedClaim,
    VerifiedClaimStatus,
    assemble_answer,
    compute_numeric_operation,
    decide_claim,
    provenance_verification,
)
from AI.qwen_adapter import QwenAIAdapter

__all__ = [
    "Answer",
    "AnswerStatus",
    "AnswerType",
    "ClaimDecision",
    "EvidenceRef",
    "GroundedClaim",
    "QwenAIAdapter",
    "VerificationResult",
    "VerificationRole",
    "VerificationVerdict",
    "VerifiedClaim",
    "VerifiedClaimStatus",
    "assemble_answer",
    "compute_numeric_operation",
    "decide_claim",
    "provenance_verification",
]
