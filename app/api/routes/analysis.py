"""Analysis-job and criterion-proposal transport routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Query, Response, status

from app.api.dependencies import ApplicationServiceDep, CurrentUserDep, IdempotencyDep
from app.api.responses import problem_responses, success_response
from app.core.exceptions import ProblemException
from app.models.domain import (
    AnalysisJob,
    AnalysisJobCreate,
    CriterionProposalReviewBatch,
    CriterionProposalReviewBatchResult,
    PaginatedCriterionProposals,
)

router = APIRouter(prefix="/api/v1")
JobId = Annotated[UUID, Path(alias="jobId")]
JobIdText = Annotated[str, Path(alias="jobId", json_schema_extra={"format": "uuid"})]
ReportId = Annotated[UUID, Path(alias="reportId")]
PageLimit = Annotated[int, Query(ge=1, le=100)]
PageCursor = Annotated[str | None, Query(max_length=2048)]


@router.post(
    "/reports/{reportId}/analysis-jobs",
    tags=["Analysis"],
    operation_id="createReportAnalysisJob",
    response_model=AnalysisJob,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        **success_response(202, created=True),
        **problem_responses(401, 404, 409, 422, 500, 503),
    },
)
async def create_report_analysis_job(
    report_id: ReportId,
    data: AnalysisJobCreate,
    response: Response,
    user: CurrentUserDep,
    idempotency: IdempotencyDep,
    service: ApplicationServiceDep,
) -> AnalysisJob:
    job = await service.create_report_analysis_job(report_id, data, user, idempotency)
    response.headers["Location"] = f"/api/v1/analysis-jobs/{job.id}"
    return job


@router.get(
    "/analysis-jobs/{jobId}",
    tags=["Analysis"],
    operation_id="getAnalysisJob",
    response_model=AnalysisJob,
    responses={**success_response(200), **problem_responses(401, 404, 500)},
)
async def get_analysis_job(
    job_id: JobIdText,
    user: CurrentUserDep,
    service: ApplicationServiceDep,
) -> AnalysisJob:
    try:
        parsed_job_id = UUID(job_id)
    except ValueError as exc:
        raise ProblemException(
            status=404,
            code="resource_not_found",
            title="Resource not found",
            detail="The analysis job does not exist.",
        ) from exc
    return await service.get_analysis_job(parsed_job_id, user)


@router.get(
    "/criterion-extraction-jobs/{jobId}/proposals",
    tags=["Criterion extraction"],
    operation_id="listCriterionExtractionProposals",
    response_model=PaginatedCriterionProposals,
    responses={
        **success_response(200),
        **problem_responses(401, 404, 409, 422, 500),
    },
)
async def list_criterion_extraction_proposals(
    job_id: JobId,
    user: CurrentUserDep,
    service: ApplicationServiceDep,
    limit: PageLimit = 50,
    cursor: PageCursor = None,
) -> PaginatedCriterionProposals:
    return await service.list_criterion_extraction_proposals(job_id, limit, cursor, user)


@router.post(
    "/criterion-extraction-jobs/{jobId}/proposal-reviews",
    tags=["Criterion extraction"],
    operation_id="createCriterionProposalReviews",
    response_model=CriterionProposalReviewBatchResult,
    status_code=status.HTTP_201_CREATED,
    responses={
        **success_response(201, created=True),
        **problem_responses(401, 404, 409, 422, 500),
    },
)
async def create_criterion_proposal_reviews(
    job_id: JobId,
    data: CriterionProposalReviewBatch,
    response: Response,
    user: CurrentUserDep,
    idempotency: IdempotencyDep,
    service: ApplicationServiceDep,
) -> CriterionProposalReviewBatchResult:
    result = await service.create_criterion_proposal_reviews(job_id, data, user, idempotency)
    response.headers["Location"] = f"/api/v1/criterion-extraction-jobs/{job_id}/proposals"
    return result
