"""Use-case port consumed by HTTP routes."""

from typing import Protocol
from uuid import UUID

from fastapi import UploadFile

from app.core.idempotency import IdempotencyContext
from app.core.security import CurrentUser
from app.models.domain import (
    AnalysisJob,
    AnalysisJobCreate,
    Criterion,
    CriterionCreate,
    CriterionExtractionJobCreate,
    CriterionProposalReviewBatch,
    CriterionProposalReviewBatchResult,
    Document,
    PaginatedCriteria,
    PaginatedCriterionProposals,
    PaginatedProjects,
    PaginatedReports,
    PaginatedValidations,
    Project,
    ProjectCreate,
    Report,
    ReportCreate,
    UserDecision,
    UserDecisionCreate,
)


class ApplicationService(Protocol):
    async def create_project(
        self, data: ProjectCreate, user: CurrentUser, idempotency: IdempotencyContext
    ) -> Project: ...

    async def list_projects(
        self, limit: int, cursor: str | None, user: CurrentUser
    ) -> PaginatedProjects: ...

    async def upload_project_document(
        self,
        project_id: UUID,
        file: UploadFile,
        display_name: str | None,
        user: CurrentUser,
        idempotency: IdempotencyContext,
    ) -> Document: ...

    async def create_project_criterion(
        self,
        project_id: UUID,
        data: CriterionCreate,
        user: CurrentUser,
        idempotency: IdempotencyContext,
    ) -> Criterion: ...

    async def list_project_criteria(
        self, project_id: UUID, limit: int, cursor: str | None, user: CurrentUser
    ) -> PaginatedCriteria: ...

    async def create_criterion_extraction_job(
        self,
        project_id: UUID,
        data: CriterionExtractionJobCreate,
        user: CurrentUser,
        idempotency: IdempotencyContext,
    ) -> AnalysisJob: ...

    async def create_project_report(
        self,
        project_id: UUID,
        data: ReportCreate,
        user: CurrentUser,
        idempotency: IdempotencyContext,
    ) -> Report: ...

    async def list_project_reports(
        self, project_id: UUID, limit: int, cursor: str | None, user: CurrentUser
    ) -> PaginatedReports: ...

    async def create_report_analysis_job(
        self,
        report_id: UUID,
        data: AnalysisJobCreate,
        user: CurrentUser,
        idempotency: IdempotencyContext,
    ) -> AnalysisJob: ...

    async def get_analysis_job(self, job_id: UUID, user: CurrentUser) -> AnalysisJob: ...

    async def list_criterion_extraction_proposals(
        self, job_id: UUID, limit: int, cursor: str | None, user: CurrentUser
    ) -> PaginatedCriterionProposals: ...

    async def create_criterion_proposal_reviews(
        self,
        job_id: UUID,
        data: CriterionProposalReviewBatch,
        user: CurrentUser,
        idempotency: IdempotencyContext,
    ) -> CriterionProposalReviewBatchResult: ...

    async def list_report_validations(
        self,
        report_id: UUID,
        limit: int,
        cursor: str | None,
        include_history: bool,
        user: CurrentUser,
    ) -> PaginatedValidations: ...

    async def create_validation_decision(
        self,
        validation_id: UUID,
        data: UserDecisionCreate,
        user: CurrentUser,
        idempotency: IdempotencyContext,
    ) -> UserDecision: ...
