"""Project, document, criterion and report transport routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Path, Query, UploadFile, status

from app.api.dependencies import ApplicationServiceDep, CurrentUserDep, IdempotencyDep
from app.api.responses import problem_responses, success_response
from app.models.domain import (
    AnalysisJob,
    Criterion,
    CriterionCreate,
    CriterionExtractionJobCreate,
    Document,
    PaginatedCriteria,
    PaginatedProjects,
    PaginatedReports,
    Project,
    ProjectCreate,
    Report,
    ReportCreate,
)

router = APIRouter(prefix="/api/v1/projects")
ProjectId = Annotated[UUID, Path(alias="projectId")]
PageLimit = Annotated[int, Query(ge=1, le=100)]
PageCursor = Annotated[str | None, Query(max_length=2048)]


@router.post(
    "",
    tags=["Projects"],
    operation_id="createProject",
    response_model=Project,
    status_code=status.HTTP_201_CREATED,
    responses={
        **success_response(201, created=True),
        **problem_responses(401, 409, 422, 500),
    },
)
async def create_project(
    data: ProjectCreate,
    user: CurrentUserDep,
    idempotency: IdempotencyDep,
    service: ApplicationServiceDep,
) -> Project:
    return await service.create_project(data, user, idempotency)


@router.get(
    "",
    tags=["Projects"],
    operation_id="listProjects",
    response_model=PaginatedProjects,
    responses={**success_response(200), **problem_responses(401, 422, 500)},
)
async def list_projects(
    user: CurrentUserDep,
    service: ApplicationServiceDep,
    limit: PageLimit = 50,
    cursor: PageCursor = None,
) -> PaginatedProjects:
    return await service.list_projects(limit, cursor, user)


@router.post(
    "/{projectId}/documents",
    tags=["Documents"],
    operation_id="uploadProjectDocument",
    response_model=Document,
    status_code=status.HTTP_201_CREATED,
    responses={
        **success_response(201, created=True),
        **problem_responses(401, 404, 409, 413, 415, 422, 500),
    },
)
async def upload_project_document(
    project_id: ProjectId,
    file: Annotated[UploadFile, File(description="PDF, DOC, DOCX, XLS sau XLSX; maximum 50 MiB.")],
    user: CurrentUserDep,
    idempotency: IdempotencyDep,
    service: ApplicationServiceDep,
    display_name: Annotated[
        str | None, Form(alias="displayName", min_length=1, max_length=255)
    ] = None,
) -> Document:
    return await service.upload_project_document(project_id, file, display_name, user, idempotency)


@router.post(
    "/{projectId}/criteria",
    tags=["Criteria"],
    operation_id="createProjectCriterion",
    response_model=Criterion,
    status_code=status.HTTP_201_CREATED,
    responses={
        **success_response(201, created=True),
        **problem_responses(401, 404, 409, 422, 500),
    },
)
async def create_project_criterion(
    project_id: ProjectId,
    data: CriterionCreate,
    user: CurrentUserDep,
    idempotency: IdempotencyDep,
    service: ApplicationServiceDep,
) -> Criterion:
    return await service.create_project_criterion(project_id, data, user, idempotency)


@router.get(
    "/{projectId}/criteria",
    tags=["Criteria"],
    operation_id="listProjectCriteria",
    response_model=PaginatedCriteria,
    responses={**success_response(200), **problem_responses(401, 404, 422, 500)},
)
async def list_project_criteria(
    project_id: ProjectId,
    user: CurrentUserDep,
    service: ApplicationServiceDep,
    limit: PageLimit = 50,
    cursor: PageCursor = None,
) -> PaginatedCriteria:
    return await service.list_project_criteria(project_id, limit, cursor, user)


@router.post(
    "/{projectId}/criterion-extraction-jobs",
    tags=["Criterion extraction"],
    operation_id="createCriterionExtractionJob",
    response_model=AnalysisJob,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        **success_response(202, created=True),
        **problem_responses(401, 404, 409, 422, 500, 503),
    },
)
async def create_criterion_extraction_job(
    project_id: ProjectId,
    data: CriterionExtractionJobCreate,
    user: CurrentUserDep,
    idempotency: IdempotencyDep,
    service: ApplicationServiceDep,
) -> AnalysisJob:
    return await service.create_criterion_extraction_job(project_id, data, user, idempotency)


@router.post(
    "/{projectId}/reports",
    tags=["Reports"],
    operation_id="createProjectReport",
    response_model=Report,
    status_code=status.HTTP_201_CREATED,
    responses={
        **success_response(201, created=True),
        **problem_responses(401, 404, 409, 422, 500),
    },
)
async def create_project_report(
    project_id: ProjectId,
    data: ReportCreate,
    user: CurrentUserDep,
    idempotency: IdempotencyDep,
    service: ApplicationServiceDep,
) -> Report:
    return await service.create_project_report(project_id, data, user, idempotency)


@router.get(
    "/{projectId}/reports",
    tags=["Reports"],
    operation_id="listProjectReports",
    response_model=PaginatedReports,
    responses={**success_response(200), **problem_responses(401, 404, 422, 500)},
)
async def list_project_reports(
    project_id: ProjectId,
    user: CurrentUserDep,
    service: ApplicationServiceDep,
    limit: PageLimit = 50,
    cursor: PageCursor = None,
) -> PaginatedReports:
    return await service.list_project_reports(project_id, limit, cursor, user)
