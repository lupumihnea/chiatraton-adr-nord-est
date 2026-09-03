"""HTTP idempotency replay/conflict enforcement."""

import hashlib
import json
from email import policy
from email.parser import BytesParser
from urllib.parse import parse_qsl

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.exceptions import ProblemException
from app.core.handlers import problem_response
from app.core.security import decode_bearer_token
from app.services.idempotency import (
    IdempotencyDisposition,
    IdempotencyScope,
    IdempotencyStore,
    IdempotencyStoreCapacityError,
    StoredHTTPResponse,
)

_EXCLUDED_REPLAY_HEADERS = {
    "connection",
    "content-length",
    "date",
    "idempotency-replayed",
    "server",
    "transfer-encoding",
    "x-request-id",
}


def _canonical_json(body: bytes) -> bytes:
    value = json.loads(body)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


def _canonical_form(body: bytes) -> bytes:
    fields = sorted(parse_qsl(body.decode("utf-8"), keep_blank_values=True))
    return json.dumps(fields, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _canonical_multipart(body: bytes, content_type: str) -> bytes:
    message = BytesParser(policy=policy.default).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body
    )
    parts: list[dict[str, str | None]] = []
    for part in message.iter_parts():
        payload = part.get_payload(decode=True) or b""
        parts.append(
            {
                "name": part.get_param("name", header="content-disposition"),
                "filename": part.get_filename(),
                "contentType": part.get_content_type(),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    parts.sort(
        key=lambda item: (
            item["name"] or "",
            item["filename"] or "",
            item["contentType"] or "",
            item["sha256"] or "",
        )
    )
    return json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def request_fingerprint(body: bytes, content_type: str, query: str) -> str:
    media_type = content_type.partition(";")[0].strip().lower()
    try:
        if media_type == "application/json":
            canonical_body = _canonical_json(body)
        elif media_type == "application/x-www-form-urlencoded":
            canonical_body = _canonical_form(body)
        elif media_type == "multipart/form-data":
            canonical_body = _canonical_multipart(body, content_type)
        else:
            canonical_body = body
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        canonical_body = body

    canonical_query = json.dumps(
        sorted(parse_qsl(query, keep_blank_values=True)), separators=(",", ":")
    ).encode("utf-8")
    digest = hashlib.sha256()
    digest.update(media_type.encode("utf-8"))
    digest.update(b"\0")
    digest.update(canonical_query)
    digest.update(b"\0")
    digest.update(canonical_body)
    return digest.hexdigest()


async def _response_body(response: Response) -> bytes:
    body = getattr(response, "body", None)
    if isinstance(body, bytes):
        return body
    return b"".join([chunk async for chunk in response.body_iterator])


def _rebuild_response(response: Response, body: bytes) -> Response:
    return Response(
        content=body,
        status_code=response.status_code,
        headers=dict(response.headers),
        background=response.background,
    )


def _stored_response(response: Response, body: bytes) -> StoredHTTPResponse:
    headers = tuple(
        (name, value)
        for name, value in response.headers.items()
        if name.lower() not in _EXCLUDED_REPLAY_HEADERS
    )
    return StoredHTTPResponse(response.status_code, body, headers)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, store: IdempotencyStore) -> None:
        super().__init__(app)
        self._store = store

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method != "POST":
            return await call_next(request)

        key = request.headers.get("Idempotency-Key")
        authorization = request.headers.get("Authorization", "")
        if not key or not key.strip() or len(key) > 255 or not authorization:
            return await call_next(request)

        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return await call_next(request)
        try:
            user = decode_bearer_token(token, request.app.state.settings)
        except ProblemException:
            return await call_next(request)

        body = await request.body()
        fingerprint = request_fingerprint(
            body, request.headers.get("Content-Type", ""), request.url.query
        )
        scope = IdempotencyScope(
            user_id=user.subject,
            method=request.method,
            resource=request.url.path,
            key=key,
        )
        try:
            decision = await self._store.begin(scope, fingerprint)
        except IdempotencyStoreCapacityError:
            return problem_response(
                request,
                status=500,
                code="internal_error",
                title="Internal server error",
                detail="The idempotency service cannot accept another operation.",
            )

        if decision.disposition == IdempotencyDisposition.CONFLICT:
            return problem_response(
                request,
                status=409,
                code="idempotency_conflict",
                title="Idempotency conflict",
                detail="This Idempotency-Key was already used with a different request.",
            )
        if decision.disposition == IdempotencyDisposition.REPLAY:
            assert decision.response is not None
            return Response(
                content=decision.response.body,
                status_code=decision.response.status_code,
                headers={
                    **dict(decision.response.headers),
                    "Idempotency-Replayed": "true",
                },
            )

        try:
            response = await call_next(request)
            response_body = await _response_body(response)
        except Exception:
            await self._store.abort(scope, fingerprint)
            raise

        rebuilt = _rebuild_response(response, response_body)
        if response.status_code >= 500:
            await self._store.abort(scope, fingerprint)
        else:
            await self._store.complete(scope, fingerprint, _stored_response(rebuilt, response_body))
        return rebuilt
