"""Exception handlers that always return RFC 9457 problem details."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import ProblemException
from app.core.request_context import request_id_from
from app.models.errors import FieldError, ProblemDetails


def _problem_type(code: str) -> str:
    return f"https://chiatraton.example/problems/{code.replace('_', '-')}"


def problem_response(
    request: Request,
    *,
    status: int,
    code: str,
    title: str,
    detail: str,
    errors: list[FieldError] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    problem_data: dict[str, Any] = {
        "type": _problem_type(code),
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        "code": code,
        "request_id": request_id_from(request),
    }
    if errors:
        problem_data["errors"] = errors
    problem = ProblemDetails(**problem_data)
    return JSONResponse(
        status_code=status,
        content=problem.model_dump(mode="json", by_alias=True, exclude_none=True),
        media_type="application/problem+json",
        headers=headers,
    )


def _field_name(location: tuple[Any, ...]) -> str:
    parts = [str(part) for part in location if part not in {"body", "query", "path", "header"}]
    prefix = str(location[0]) if location else "request"
    return ".".join([prefix, *parts])[:255]


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemException)
    async def problem_exception_handler(request: Request, exc: ProblemException) -> JSONResponse:
        return problem_response(
            request,
            status=exc.status,
            code=exc.code,
            title=exc.title,
            detail=exc.detail,
            errors=exc.errors,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            FieldError(
                field=_field_name(tuple(error.get("loc", ()))),
                code=str(error.get("type", "invalid_value"))[:100],
                message=str(error.get("msg", "Invalid value"))[:1000],
            )
            for error in exc.errors()[:100]
        ]
        return problem_response(
            request,
            status=422,
            code="validation_error",
            title="Request validation failed",
            detail="One or more request fields are invalid.",
            errors=errors,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "resource_not_found" if exc.status_code == 404 else "http_error"
        title = "Resource not found" if exc.status_code == 404 else "HTTP error"
        detail = str(exc.detail) if exc.detail else title
        return problem_response(
            request,
            status=exc.status_code,
            code=code,
            title=title,
            detail=detail,
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request.app.state.logger.exception(
            "Unhandled API error", extra={"exception_type": type(exc).__name__}
        )
        return problem_response(
            request,
            status=500,
            code="internal_error",
            title="Internal server error",
            detail="The server could not complete the request.",
        )
