"""Public health endpoint."""

from fastapi import APIRouter, Request

from app.api.responses import problem_responses, success_response
from app.core.config import Settings
from app.models.domain import Health

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    operation_id="getHealth",
    response_model=Health,
    status_code=200,
    responses={**success_response(200), **problem_responses(429, 500)},
)
async def get_health(request: Request) -> Health:
    settings: Settings = request.app.state.settings
    return Health(status="ok", service="chiatraton-api", version=settings.app_version)
