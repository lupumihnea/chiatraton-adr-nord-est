"""RFC 9457 error models."""

from pydantic import Field

from app.models.base import APIModel


class FieldError(APIModel):
    field: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=1000)


class ProblemDetails(APIModel):
    type: str = Field(min_length=1, json_schema_extra={"format": "uri"})
    title: str = Field(min_length=1, max_length=255)
    status: int = Field(ge=400, le=599)
    detail: str = Field(min_length=1, max_length=2000)
    instance: str = Field(min_length=1, json_schema_extra={"format": "uri-reference"})
    code: str = Field(min_length=1, max_length=100)
    request_id: str = Field(min_length=1, max_length=128)
    errors: list[FieldError] = Field(default=None, max_length=100)  # type: ignore[assignment]
