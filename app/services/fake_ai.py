"""Deterministic, synthetic AI adapters for local demonstrations only."""

from __future__ import annotations

import hashlib

from app.models.domain import AIOutcome, SourceAnchor
from app.services.ports import (
    CriterionExtractionRequest,
    CriterionProposalCandidate,
    ReportAnalysisRequest,
    ValidationCandidate,
)


class DeterministicFakeCriterionExtractor:
    def __init__(self, *, invalid_response: bool = False) -> None:
        self._invalid_response = invalid_response

    async def extract(
        self, request: CriterionExtractionRequest
    ) -> list[CriterionProposalCandidate]:
        first_document = sorted(request.documents, key=lambda item: str(item.metadata.id))[0]
        prefix = hashlib.sha256(str(request.project_id).encode()).hexdigest()[:8].upper()
        proposals: list[CriterionProposalCandidate] = []
        for index in range(1, 4):
            anchors = (
                SourceAnchor(
                    document_id=first_document.metadata.id,
                    page_number=1,
                    passage=f"Synthetic criterion evidence {index} for the local demonstration.",
                ),
            )
            if self._invalid_response and index == 1:
                anchors = ()
            proposals.append(
                CriterionProposalCandidate(
                    client_reference=f"fake-proposal-{index}",
                    code=f"AUTO-{prefix}-{index:02d}",
                    description=(
                        f"Synthetic monitoring criterion {index} generated for demonstration."
                    ),
                    deadline=None,
                    source_anchors=anchors,
                )
            )
        return proposals


class DeterministicFakeReportAnalyzer:
    def __init__(self, *, invalid_response: bool = False) -> None:
        self._invalid_response = invalid_response

    async def analyze(self, request: ReportAnalysisRequest) -> list[ValidationCandidate]:
        report_document_ids = {item.document_id for item in request.report.documents}
        evidence = next(
            item for item in request.allowed_documents if item.metadata.id in report_document_ids
        )
        outcomes = (
            AIOutcome.COMPLIANT,
            AIOutcome.PARTIALLY_COMPLIANT,
            AIOutcome.NON_COMPLIANT,
        )
        results: list[ValidationCandidate] = []
        for index, criterion in enumerate(request.criteria):
            anchors = (
                SourceAnchor(
                    document_id=evidence.metadata.id,
                    page_number=1,
                    passage=(
                        f"Synthetic report evidence for criterion {criterion.code}; "
                        "no beneficiary data is used."
                    ),
                ),
            )
            if self._invalid_response and index == 0:
                anchors = ()
            results.append(
                ValidationCandidate(
                    criterion_id=criterion.id,
                    criterion_version=criterion.version,
                    outcome=outcomes[index % len(outcomes)],
                    rationale=(
                        "Deterministic synthetic rationale produced by the local fake adapter."
                    ),
                    source_anchors=anchors,
                )
            )
        return results
