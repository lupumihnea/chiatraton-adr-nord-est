"""Validation shared by every POST operation."""

from typing import Annotated

from fastapi import Header
from pydantic import BaseModel, ConfigDict, Field

from app.core.exceptions import ProblemException
from app.models.errors import FieldError


class IdempotencyContext(BaseModel):
    model_config = ConfigDict(frozen=True)
    key: str = Field(min_length=1, max_length=255)


async def require_idempotency_key(
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=1,
            max_length=255,
            description="Cheie opacă pentru replay sigur al operației POST.",
        ),
    ],
) -> IdempotencyContext:
    if not idempotency_key.strip():
        raise ProblemException(
            status=422,
            code="validation_error",
            title="Request validation failed",
            detail="Idempotency-Key must contain a non-whitespace value.",
            errors=[
                FieldError(
                    field="header.Idempotency-Key",
                    code="string_blank",
                    message="Value must not be blank.",
                )
            ],
        )
    return IdempotencyContext(key=idempotency_key)
