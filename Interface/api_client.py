"""Shared asynchronous HTTP client used by the NiceGUI frontend."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx

DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"


@dataclass(frozen=True, slots=True)
class ProblemDetails:
    """RFC 9457 response returned by the API."""

    type: str
    title: str
    status: int
    detail: str
    instance: str
    code: str
    request_id: str
    errors: tuple[dict[str, Any], ...] = ()

    @classmethod
    def from_payload(cls, payload: dict[str, Any], status_code: int) -> ProblemDetails:
        raw_errors = payload.get("errors")
        errors = tuple(item for item in raw_errors or () if isinstance(item, dict))
        return cls(
            type=str(payload.get("type", "about:blank")),
            title=str(payload.get("title", "Request failed")),
            status=int(payload.get("status", status_code)),
            detail=str(payload.get("detail", "The API request failed.")),
            instance=str(payload.get("instance", "")),
            code=str(payload.get("code", "http_error")),
            request_id=str(payload.get("requestId", "")),
            errors=errors,
        )


class APIClientError(RuntimeError):
    """Base error safe to display in the UI."""


class APIConfigurationError(APIClientError):
    """The UI is missing required runtime configuration."""


class APIUnavailableError(APIClientError):
    """The API could not be reached."""


class APIProblemError(APIClientError):
    """An API request returned a ProblemDetails response."""

    def __init__(self, problem: ProblemDetails) -> None:
        self.problem = problem
        super().__init__(problem.detail)


def api_error_message(error: Exception) -> str:
    """Return a concise, non-sensitive message suitable for a notification."""

    if isinstance(error, APIProblemError):
        suffix = f" (cod: {error.problem.code})" if error.problem.code else ""
        return f"{error.problem.detail}{suffix}"
    if isinstance(error, APIClientError):
        return str(error)
    return "A apărut o eroare neașteptată în interfață."


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def json_fingerprint(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def upload_fingerprint(
    *,
    project_id: str,
    filename: str,
    content_type: str,
    content: bytes,
    display_name: str | None,
) -> str:
    metadata = {
        "projectId": project_id,
        "filename": filename,
        "contentType": content_type,
        "displayName": display_name,
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    return json_fingerprint(metadata)


class IdempotencyKeyManager:
    """Keeps a POST key stable while the same payload is being retried."""

    def __init__(self) -> None:
        self._pending: dict[str, tuple[str, str]] = {}

    def key_for(self, operation: str, fingerprint: str) -> str:
        pending = self._pending.get(operation)
        if pending is not None and pending[0] == fingerprint:
            return pending[1]
        key = str(uuid4())
        self._pending[operation] = (fingerprint, key)
        return key

    def mark_succeeded(self, operation: str, fingerprint: str) -> None:
        pending = self._pending.get(operation)
        if pending is not None and pending[0] == fingerprint:
            del self._pending[operation]


class ChIAtratonAPIClient:
    """Typed facade over one reusable ``httpx.AsyncClient`` instance."""

    def __init__(
        self,
        *,
        base_url: str,
        bearer_token: str,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        normalized_url = base_url.strip().rstrip("/")
        if not normalized_url:
            raise APIConfigurationError("CHIATRATON_API_BASE_URL nu poate fi gol.")
        self._bearer_token = bearer_token.strip()
        self._client = httpx.AsyncClient(
            base_url=normalized_url,
            timeout=timeout_seconds,
            transport=transport,
            follow_redirects=False,
            trust_env=False,
        )

    @classmethod
    def from_environment(cls) -> ChIAtratonAPIClient:
        return cls(
            base_url=os.getenv("CHIATRATON_API_BASE_URL", DEFAULT_API_BASE_URL),
            bearer_token=os.getenv("CHIATRATON_UI_BEARER_TOKEN", ""),
        )

    @property
    def base_url(self) -> str:
        return str(self._client.base_url).rstrip("/")

    async def close(self) -> None:
        await self._client.aclose()

    def _authorization_headers(self) -> dict[str, str]:
        if not self._bearer_token:
            raise APIConfigurationError(
                "Configurează CHIATRATON_UI_BEARER_TOKEN înainte de a folosi interfața."
            )
        return {"Authorization": f"Bearer {self._bearer_token}"}

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = {**self._authorization_headers(), **kwargs.pop("headers", {})}
        try:
            response = await self._client.request(method, path, headers=headers, **kwargs)
        except httpx.RequestError as exc:
            raise APIUnavailableError(
                f"API-ul nu este disponibil la {self.base_url}."
            ) from exc
        if response.is_error:
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            if not isinstance(payload, dict):
                payload = {}
            raise APIProblemError(ProblemDetails.from_payload(payload, response.status_code))
        return response

    async def list_projects(
        self, *, limit: int = 50, cursor: str | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        response = await self._request("GET", "/api/v1/projects", params=params)
        payload = response.json()
        if not isinstance(payload, dict):
            raise APIClientError("API-ul a returnat o listă de proiecte invalidă.")
        return payload

    async def list_all_projects(self) -> list[dict[str, Any]]:
        projects: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            page = await self.list_projects(limit=100, cursor=cursor)
            items = page.get("items", [])
            if not isinstance(items, list):
                raise APIClientError("API-ul a returnat proiecte într-un format invalid.")
            projects.extend(item for item in items if isinstance(item, dict))
            next_cursor = page.get("nextCursor")
            if not next_cursor:
                return projects
            cursor = str(next_cursor)

    async def get_project(self, project_id: str) -> dict[str, Any] | None:
        projects = await self.list_all_projects()
        return next((item for item in projects if item.get("id") == project_id), None)

    async def create_project(
        self, payload: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]:
        response = await self._request(
            "POST",
            "/api/v1/projects",
            json=payload,
            headers={"Idempotency-Key": idempotency_key},
        )
        result = response.json()
        if not isinstance(result, dict):
            raise APIClientError("API-ul a returnat un proiect invalid.")
        return result

    async def upload_document(
        self,
        project_id: str,
        *,
        filename: str,
        content: bytes,
        content_type: str,
        display_name: str | None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        data = {"displayName": display_name} if display_name else {}
        response = await self._request(
            "POST",
            f"/api/v1/projects/{project_id}/documents",
            data=data,
            files={"file": (filename, content, content_type)},
            headers={"Idempotency-Key": idempotency_key},
        )
        result = response.json()
        if not isinstance(result, dict):
            raise APIClientError("API-ul a returnat un document invalid.")
        return result


api_client = ChIAtratonAPIClient.from_environment()
