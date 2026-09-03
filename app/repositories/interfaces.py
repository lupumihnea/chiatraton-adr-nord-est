"""Repository ports owned by the API layer."""

from typing import Protocol
from uuid import UUID

from app.models.domain import (
    AnalysisJob,
    Criterion,
    CriterionProposal,
    CriterionValidation,
    Document,
    Project,
    Report,
    UserDecision,
)


class ProjectRepository(Protocol):
    async def get(self, project_id: UUID) -> Project | None: ...

    async def save(self, project: Project) -> Project: ...


class DocumentRepository(Protocol):
    async def get(self, document_id: UUID) -> Document | None: ...

    async def save(self, document: Document) -> Document: ...


class CriterionRepository(Protocol):
    async def get(self, criterion_id: UUID) -> Criterion | None: ...

    async def save(self, criterion: Criterion) -> Criterion: ...


class ReportRepository(Protocol):
    async def get(self, report_id: UUID) -> Report | None: ...

    async def save(self, report: Report) -> Report: ...


class AnalysisJobRepository(Protocol):
    async def get(self, job_id: UUID) -> AnalysisJob | None: ...

    async def save(self, job: AnalysisJob) -> AnalysisJob: ...

    async def list_proposals(self, job_id: UUID) -> list[CriterionProposal]: ...


class ValidationRepository(Protocol):
    async def get(self, validation_id: UUID) -> CriterionValidation | None: ...

    async def save_decision(self, decision: UserDecision) -> UserDecision: ...
