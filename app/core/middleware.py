from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from app.core.request_context import accepted_request_id


async def request_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request.state.request_id = accepted_request_id(request)
    response = await call_next(request)
    response.headers["X-Request-Id"] = request.state.request_id
    return response
