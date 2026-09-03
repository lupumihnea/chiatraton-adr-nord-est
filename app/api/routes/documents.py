"""Document content transport routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Response

from app.api.dependencies import ApplicationServiceDep, CurrentUserDep
from app.api.responses import REQUEST_ID_HEADER, problem_responses

router = APIRouter(prefix="/api/v1/documents")
DocumentId = Annotated[UUID, Path(alias="documentId")]


@router.get(
    "/{documentId}/content",
    tags=["Documents"],
    operation_id="getDocumentContent",
    responses={
        200: {
            "description": "Successful Response",
            "headers": {"X-Request-Id": REQUEST_ID_HEADER},
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
        },
        **problem_responses(401, 404, 422, 500),
    },
)
async def get_document_content(
    document_id: DocumentId,
    user: CurrentUserDep,
    service: ApplicationServiceDep,
) -> Response:
    document, content = await service.get_document_content(document_id, user)
    return Response(
        content=content,
        media_type=document.media_type.value,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{document.original_filename}"'
            ),
        },
    )
