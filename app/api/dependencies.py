"""Typed dependencies shared by route modules."""

from typing import Annotated

from fastapi import Depends

from app.core.idempotency import IdempotencyContext, require_idempotency_key
from app.core.security import CurrentUser, get_current_user
from app.services.interfaces import ApplicationService
from app.services.stubs import UnimplementedApplicationService

_stub_service = UnimplementedApplicationService()


def get_application_service() -> ApplicationService:
    return _stub_service


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
IdempotencyDep = Annotated[IdempotencyContext, Depends(require_idempotency_key)]
ApplicationServiceDep = Annotated[ApplicationService, Depends(get_application_service)]
