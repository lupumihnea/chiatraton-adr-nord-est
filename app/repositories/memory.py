"""Transactional in-memory repository adapters for tests and demonstrations."""

from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass, field
from types import TracebackType
from uuid import UUID

from app.models.domain import (
    AnalysisJob,
    Criterion,
    CriterionProposal,
    CriterionProposalReviewRecord,
    CriterionValidation,
    Document,
    Project,
    Report,
    UserDecision,
)


@dataclass
class InMemoryState:
    projects: dict[UUID, Project] = field(default_factory=dict)
    project_owners: dict[UUID, str] = field(default_factory=dict)
    documents: dict[UUID, Document] = field(default_factory=dict)
    criteria: dict[UUID, Criterion] = field(default_factory=dict)
    criterion_history: dict[UUID, list[Criterion]] = field(default_factory=dict)
    criterion_snapshot_versions: dict[UUID, int] = field(default_factory=dict)
    reports: dict[UUID, Report] = field(default_factory=dict)
    jobs: dict[UUID, AnalysisJob] = field(default_factory=dict)
    job_criteria_snapshots: dict[UUID, list[Criterion]] = field(default_factory=dict)
    proposals: dict[UUID, CriterionProposal] = field(default_factory=dict)
    proposal_reviews: dict[UUID, CriterionProposalReviewRecord] = field(default_factory=dict)
    validations: dict[UUID, CriterionValidation] = field(default_factory=dict)
    decisions: dict[UUID, UserDecision] = field(default_factory=dict)


class InMemoryStore:
    """Shared state. Each unit of work holds the lock for one atomic transaction."""

    def __init__(self) -> None:
        self.state = InMemoryState()
        self.lock = asyncio.Lock()


class _Projects:
    def __init__(self, state: InMemoryState) -> None:
        self._state = state

    async def get(self, project_id: UUID) -> Project | None:
        return self._state.projects.get(project_id)

    async def owner(self, project_id: UUID) -> str | None:
        return self._state.project_owners.get(project_id)

    async def add(self, project: Project, owner: str) -> None:
        if project.id in self._state.projects:
            raise RuntimeError("Project identifiers are append-only")
        self._state.projects[project.id] = project
        self._state.project_owners[project.id] = owner

    async def list_for_owner(self, owner: str) -> list[Project]:
        return [
            project
            for project_id, project in self._state.projects.items()
            if self._state.project_owners.get(project_id) == owner
        ]


class _Documents:
    def __init__(self, state: InMemoryState) -> None:
        self._state = state

    async def get(self, document_id: UUID) -> Document | None:
        return self._state.documents.get(document_id)

    async def add(self, document: Document) -> None:
        if document.id in self._state.documents:
            raise RuntimeError("Document identifiers are append-only")
        self._state.documents[document.id] = document

    async def list_for_project(self, project_id: UUID) -> list[Document]:
        return [item for item in self._state.documents.values() if item.project_id == project_id]

    async def find_by_sha256(self, project_id: UUID, sha256: str) -> Document | None:
        return next(
            (
                item
                for item in self._state.documents.values()
                if item.project_id == project_id and item.sha256 == sha256
            ),
            None,
        )


class _Criteria:
    def __init__(self, state: InMemoryState) -> None:
        self._state = state

    async def get(self, criterion_id: UUID) -> Criterion | None:
        return self._state.criteria.get(criterion_id)

    async def add(self, criterion: Criterion) -> None:
        if criterion.id in self._state.criteria:
            raise RuntimeError("Criterion versions are append-only")
        self._state.criteria[criterion.id] = criterion
        self._state.criterion_history.setdefault(criterion.id, []).append(criterion)
        self._state.criterion_snapshot_versions[criterion.project_id] = (
            self._state.criterion_snapshot_versions.get(criterion.project_id, 0) + 1
        )

    async def list_for_project(self, project_id: UUID) -> list[Criterion]:
        return [item for item in self._state.criteria.values() if item.project_id == project_id]

    async def code_exists(self, project_id: UUID, normalized_code: str) -> bool:
        return any(
            item.project_id == project_id and item.code.strip().casefold() == normalized_code
            for item in self._state.criteria.values()
        )

    async def active_snapshot(self, project_id: UUID) -> tuple[int, list[Criterion]]:
        criteria = [
            item
            for item in self._state.criteria.values()
            if item.project_id == project_id and item.active
        ]
        version = self._state.criterion_snapshot_versions.get(project_id, 0)
        return version, criteria


class _Reports:
    def __init__(self, state: InMemoryState) -> None:
        self._state = state

    async def get(self, report_id: UUID) -> Report | None:
        return self._state.reports.get(report_id)

    async def add(self, report: Report) -> None:
        if report.id in self._state.reports:
            raise RuntimeError("Report identifiers are append-only")
        self._state.reports[report.id] = report

    async def update(self, report: Report) -> None:
        self._state.reports[report.id] = report

    async def list_for_project(self, project_id: UUID) -> list[Report]:
        return [item for item in self._state.reports.values() if item.project_id == project_id]

    async def external_identity_exists(
        self, project_id: UUID, external_system: str, external_id: str
    ) -> bool:
        return any(
            item.project_id == project_id
            and item.external_system is not None
            and item.external_system.value == external_system
            and item.external_id == external_id
            for item in self._state.reports.values()
        )


class _Jobs:
    def __init__(self, state: InMemoryState) -> None:
        self._state = state

    async def get(self, job_id: UUID) -> AnalysisJob | None:
        return self._state.jobs.get(job_id)

    async def add(self, job: AnalysisJob) -> None:
        if job.id in self._state.jobs:
            raise RuntimeError("AnalysisJob identifiers are append-only")
        self._state.jobs[job.id] = job

    async def update(self, job: AnalysisJob) -> None:
        self._state.jobs[job.id] = job

    async def set_criteria_snapshot(self, job_id: UUID, criteria: list[Criterion]) -> None:
        self._state.job_criteria_snapshots[job_id] = copy.deepcopy(criteria)

    async def get_criteria_snapshot(self, job_id: UUID) -> list[Criterion]:
        return copy.deepcopy(self._state.job_criteria_snapshots.get(job_id, []))


class _Proposals:
    def __init__(self, state: InMemoryState) -> None:
        self._state = state

    async def get(self, proposal_id: UUID) -> CriterionProposal | None:
        return self._state.proposals.get(proposal_id)

    async def add_many(self, proposals: list[CriterionProposal]) -> None:
        for proposal in proposals:
            if proposal.id in self._state.proposals:
                raise RuntimeError("CriterionProposal identifiers are append-only")
            self._state.proposals[proposal.id] = proposal

    async def list_for_job(self, job_id: UUID) -> list[CriterionProposal]:
        return [item for item in self._state.proposals.values() if item.analysis_job_id == job_id]

    async def get_review(self, proposal_id: UUID) -> CriterionProposalReviewRecord | None:
        return self._state.proposal_reviews.get(proposal_id)

    async def add_review(self, review: CriterionProposalReviewRecord) -> None:
        if review.proposal_id in self._state.proposal_reviews:
            raise RuntimeError("CriterionProposal reviews are final and append-only")
        self._state.proposal_reviews[review.proposal_id] = review


class _Validations:
    def __init__(self, state: InMemoryState) -> None:
        self._state = state

    async def get(self, validation_id: UUID) -> CriterionValidation | None:
        return self._state.validations.get(validation_id)

    async def add_many(self, validations: list[CriterionValidation]) -> None:
        for validation in validations:
            if validation.id in self._state.validations:
                raise RuntimeError("CriterionValidation identifiers are append-only")
            self._state.validations[validation.id] = validation

    async def list_for_report(self, report_id: UUID) -> list[CriterionValidation]:
        return [item for item in self._state.validations.values() if item.report_id == report_id]

    async def get_decision(self, validation_id: UUID) -> UserDecision | None:
        return self._state.decisions.get(validation_id)

    async def add_decision(self, decision: UserDecision) -> None:
        if decision.validation_id in self._state.decisions:
            raise RuntimeError("UserDecision records are append-only")
        self._state.decisions[decision.validation_id] = decision


class InMemoryUnitOfWork:
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store
        self._state: InMemoryState | None = None

    async def __aenter__(self) -> InMemoryUnitOfWork:
        await self._store.lock.acquire()
        self._state = copy.deepcopy(self._store.state)
        self.projects = _Projects(self._state)
        self.documents = _Documents(self._state)
        self.criteria = _Criteria(self._state)
        self.reports = _Reports(self._state)
        self.jobs = _Jobs(self._state)
        self.proposals = _Proposals(self._state)
        self.validations = _Validations(self._state)
        return self

    async def commit(self) -> None:
        if self._state is None:
            raise RuntimeError("UnitOfWork is not active")
        self._store.state = self._state

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        self._state = None
        self._store.lock.release()


class InMemoryUnitOfWorkFactory:
    def __init__(self, store: InMemoryStore | None = None) -> None:
        self.store = store or InMemoryStore()

    def __call__(self) -> InMemoryUnitOfWork:
        return InMemoryUnitOfWork(self.store)
