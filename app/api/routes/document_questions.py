"""Synchronous factual question answering over documents owned by one project."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path

from app.api.dependencies import ApplicationServiceDep, CurrentUserDep, IdempotencyDep
from app.api.responses import problem_responses, success_response
from app.models.domain import DocumentQuestionAnswer, DocumentQuestionCreate

router = APIRouter(prefix="/api/v1/projects")
ProjectId = Annotated[UUID, Path(alias="projectId")]


@router.post(
    "/{projectId}/document-questions",
    tags=["Document questions"],
    operation_id="askProjectDocuments",
    response_model=DocumentQuestionAnswer,
    responses={
        **success_response(200),
        **problem_responses(401, 404, 422, 500, 503),
    },
)
async def ask_project_documents(
    project_id: ProjectId,
    data: DocumentQuestionCreate,
    user: CurrentUserDep,
    idempotency: IdempotencyDep,
    service: ApplicationServiceDep,
) -> DocumentQuestionAnswer:
    return await service.ask_project_documents(project_id, data, user, idempotency)
