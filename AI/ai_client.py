from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class EvidenceAnchor:
    evidence_id: str
    role: str
    document_id: int
    page: int | None
    text: str
    chapter: str | None = None
    subchapter: str | None = None
    report_id: int | None = None


@dataclass
class CriterionInput:
    criterion_id: int
    description: str
    deadline: str | None
    importance: int | None
    baseline_sources: list[EvidenceAnchor] = field(default_factory=list)


@dataclass
class ReportInput:
    report_id: int
    document_id: int
    kind: str
    period_start: str
    period_end: str
    path: str


@dataclass
class ValidationProposal:
    criterion_id: int
    applicable: bool
    outcome: str
    rationale: str
    sources: list[EvidenceAnchor]
    warnings: list[str] = field(default_factory=list)


class AIClient(Protocol):
    model_name: str

    def analyze_report(
        self,
        report: ReportInput,
        criteria: list[CriterionInput],
        project_documents: list[tuple[int, str]],
        previous_reports: list[ReportInput],
    ) -> list[ValidationProposal]:
        ...
