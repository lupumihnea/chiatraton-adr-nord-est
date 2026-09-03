"""Criterion validation and human-decision transport routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Query, Response, status

from app.api.dependencies import ApplicationServiceDep, CurrentUserDep, IdempotencyDep
from app.api.responses import problem_responses, success_response
from app.models.domain import PaginatedValidations, UserDecision, UserDecisionCreate

router = APIRouter(prefix="/api/v1")
ReportId = Annotated[UUID, Path(alias="reportId")]
ValidationId = Annotated[UUID, Path(alias="validationId")]
PageLimit = Annotated[int, Query(ge=1, le=100)]
PageCursor = Annotated[str | None, Query(max_length=2048)]


@router.get(
    "/reports/{reportId}/validations",
    tags=["Validations"],
    operation_id="listReportValidations",
    response_model=PaginatedValidations,
    responses={**success_response(200), **problem_responses(401, 404, 422, 500)},
)
async def list_report_validations(
    report_id: ReportId,
    user: CurrentUserDep,
    service: ApplicationServiceDep,
    limit: PageLimit = 50,
    cursor: PageCursor = None,
    include_history: Annotated[bool, Query(alias="includeHistory")] = False,
) -> PaginatedValidations:
    return await service.list_report_validations(report_id, limit, cursor, include_history, user)


@router.post(
    "/validations/{validationId}/decisions",
    tags=["Validations"],
    operation_id="createValidationDecision",
    response_model=UserDecision,
    status_code=status.HTTP_201_CREATED,
    responses={
        **success_response(201, created=True),
        **problem_responses(401, 404, 409, 422, 500),
    },
)
async def create_validation_decision(
    validation_id: ValidationId,
    data: UserDecisionCreate,
    response: Response,
    user: CurrentUserDep,
    idempotency: IdempotencyDep,
    service: ApplicationServiceDep,
) -> UserDecision:
    decision = await service.create_validation_decision(validation_id, data, user, idempotency)
    response.headers["Location"] = f"/api/v1/validations/{validation_id}/decisions"
    return decision
