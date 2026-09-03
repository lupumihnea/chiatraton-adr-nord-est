"""Typed dependencies shared by route modules."""

from typing import Annotated

from fastapi import Depends, Request

from app.core.idempotency import IdempotencyContext, require_idempotency_key
from app.core.security import CurrentUser, get_current_user
from app.services.interfaces import ApplicationService


def get_application_service(request: Request) -> ApplicationService:
    return request.app.state.application_service


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
IdempotencyDep = Annotated[IdempotencyContext, Depends(require_idempotency_key)]
ApplicationServiceDep = Annotated[ApplicationService, Depends(get_application_service)]
