"""Shared asynchronous HTTP client used by the NiceGUI frontend."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx
from dotenv import load_dotenv

load_dotenv()

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


class APITimeoutError(APIClientError):
    """The API was reachable but did not answer before the client timeout."""


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
        except httpx.TimeoutException as exc:
            raise APITimeoutError(
                f"API-ul de la {self.base_url} este disponibil, dar răspunsul a depășit "
                "timpul de așteptare. Operația AI continuă în fundal dacă job-ul a fost creat."
            ) from exc
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

    async def list_project_documents(
        self,
        project_id: str,
        *,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        response = await self._request(
            "GET",
            f"/api/v1/projects/{project_id}/documents",
            params=params,
        )
        result = response.json()
        if not isinstance(result, dict):
            raise APIClientError("API-ul a returnat documente într-un format invalid.")
        return result

    async def list_all_project_documents(self, project_id: str) -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            page = await self.list_project_documents(project_id, limit=100, cursor=cursor)
            items = page.get("items", [])
            if not isinstance(items, list):
                raise APIClientError("API-ul a returnat documente într-un format invalid.")
            documents.extend(item for item in items if isinstance(item, dict))
            next_cursor = page.get("nextCursor")
            if not next_cursor:
                return documents
            cursor = str(next_cursor)

    async def get_document_content(self, document_id: str) -> tuple[bytes, str | None]:
        response = await self._request("GET", f"/api/v1/documents/{document_id}/content")
        content_disposition = response.headers.get("content-disposition")
        filename = None
        if content_disposition and "filename=" in content_disposition:
            filename = content_disposition.split("filename=", 1)[1].strip('"')
        return response.content, filename

    async def create_criterion_extraction_job(
        self,
        project_id: str,
        *,
        document_ids: list[str],
        idempotency_key: str,
    ) -> dict[str, Any]:
        response = await self._request(
            "POST",
            f"/api/v1/projects/{project_id}/criterion-extraction-jobs",
            json={"documentIds": document_ids},
            headers={"Idempotency-Key": idempotency_key},
            # Job creation should normally return immediately with HTTP 202,
            # but the local demo process can be briefly busy while the first
            # embedding model is initialized. Keep this POST tolerant; the
            # Idempotency-Key makes retries safe.
            timeout=180.0,
        )
        result = response.json()
        if not isinstance(result, dict):
            raise APIClientError("API-ul a returnat un job de extracție invalid.")
        return result

    async def get_analysis_job(self, job_id: str) -> dict[str, Any]:
        response = await self._request("GET", f"/api/v1/analysis-jobs/{job_id}")
        result = response.json()
        if not isinstance(result, dict):
            raise APIClientError("API-ul a returnat un job de analiză invalid.")
        return result

    async def list_criterion_extraction_proposals(
        self,
        job_id: str,
        *,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        response = await self._request(
            "GET",
            f"/api/v1/criterion-extraction-jobs/{job_id}/proposals",
            params=params,
        )
        result = response.json()
        if not isinstance(result, dict):
            raise APIClientError("API-ul a returnat propuneri de obligații invalide.")
        return result

    async def list_all_criterion_extraction_proposals(
        self, job_id: str
    ) -> list[dict[str, Any]]:
        proposals: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            page = await self.list_criterion_extraction_proposals(
                job_id, limit=100, cursor=cursor
            )
            items = page.get("items", [])
            if not isinstance(items, list):
                raise APIClientError("API-ul a returnat propuneri într-un format invalid.")
            proposals.extend(item for item in items if isinstance(item, dict))
            next_cursor = page.get("nextCursor")
            if not next_cursor:
                return proposals
            cursor = str(next_cursor)

    async def review_criterion_proposals(
        self,
        job_id: str,
        *,
        reviews: list[dict[str, Any]],
        idempotency_key: str,
    ) -> dict[str, Any]:
        response = await self._request(
            "POST",
            f"/api/v1/criterion-extraction-jobs/{job_id}/proposal-reviews",
            json={"reviews": reviews},
            headers={"Idempotency-Key": idempotency_key},
        )
        result = response.json()
        if not isinstance(result, dict):
            raise APIClientError("API-ul a returnat un rezultat de revizuire invalid.")
        return result

    async def list_project_criteria(
        self,
        project_id: str,
        *,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        response = await self._request(
            "GET",
            f"/api/v1/projects/{project_id}/criteria",
            params=params,
        )
        result = response.json()
        if not isinstance(result, dict):
            raise APIClientError("API-ul a returnat obligații într-un format invalid.")
        return result

    async def list_all_project_criteria(self, project_id: str) -> list[dict[str, Any]]:
        criteria: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            page = await self.list_project_criteria(project_id, limit=100, cursor=cursor)
            items = page.get("items", [])
            if not isinstance(items, list):
                raise APIClientError("API-ul a returnat obligații într-un format invalid.")
            criteria.extend(item for item in items if isinstance(item, dict))
            next_cursor = page.get("nextCursor")
            if not next_cursor:
                return criteria
            cursor = str(next_cursor)


    async def create_project_report(
        self,
        project_id: str,
        *,
        period_start: str,
        period_end: str,
        document_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        payload = {
            "reportType": "implementation_progress",
            "periodStart": period_start,
            "periodEnd": period_end,
            "documents": [{"documentId": document_id, "role": "main_report"}],
        }
        response = await self._request(
            "POST",
            f"/api/v1/projects/{project_id}/reports",
            json=payload,
            headers={"Idempotency-Key": idempotency_key},
        )
        result = response.json()
        if not isinstance(result, dict):
            raise APIClientError("API-ul a returnat un raport invalid.")
        return result

    async def list_project_reports(
        self,
        project_id: str,
        *,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        response = await self._request(
            "GET", f"/api/v1/projects/{project_id}/reports", params=params
        )
        result = response.json()
        if not isinstance(result, dict):
            raise APIClientError("API-ul a returnat rapoarte într-un format invalid.")
        return result

    async def list_all_project_reports(self, project_id: str) -> list[dict[str, Any]]:
        reports: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            page = await self.list_project_reports(project_id, limit=100, cursor=cursor)
            items = page.get("items", [])
            if not isinstance(items, list):
                raise APIClientError("API-ul a returnat rapoarte într-un format invalid.")
            reports.extend(item for item in items if isinstance(item, dict))
            next_cursor = page.get("nextCursor")
            if not next_cursor:
                return reports
            cursor = str(next_cursor)

    async def create_report_analysis_job(
        self,
        report_id: str,
        *,
        idempotency_key: str,
        project_document_ids: list[str] | None = None,
        previous_report_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        response = await self._request(
            "POST",
            f"/api/v1/reports/{report_id}/analysis-jobs",
            json={
                "projectDocumentIds": project_document_ids or [],
                "previousReportIds": previous_report_ids or [],
            },
            headers={"Idempotency-Key": idempotency_key},
            timeout=180.0,
        )
        result = response.json()
        if not isinstance(result, dict):
            raise APIClientError("API-ul a returnat un job de analiză a progresului invalid.")
        return result

    async def list_report_validations(
        self,
        report_id: str,
        *,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit, "includeHistory": False}
        if cursor is not None:
            params["cursor"] = cursor
        response = await self._request(
            "GET", f"/api/v1/reports/{report_id}/validations", params=params
        )
        result = response.json()
        if not isinstance(result, dict):
            raise APIClientError("API-ul a returnat rezultate de progres invalide.")
        return result

    async def list_all_report_validations(self, report_id: str) -> list[dict[str, Any]]:
        validations: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            page = await self.list_report_validations(report_id, limit=100, cursor=cursor)
            items = page.get("items", [])
            if not isinstance(items, list):
                raise APIClientError("API-ul a returnat rezultate de progres invalide.")
            validations.extend(item for item in items if isinstance(item, dict))
            next_cursor = page.get("nextCursor")
            if not next_cursor:
                return validations
            cursor = str(next_cursor)

    async def create_validation_decision(
        self,
        validation_id: str,
        *,
        validation_revision: int,
        action: str,
        idempotency_key: str,
        final_outcome: str | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "action": action,
            "validationRevision": validation_revision,
        }
        if final_outcome is not None:
            payload["finalOutcome"] = final_outcome
        if comment is not None:
            payload["comment"] = comment
        response = await self._request(
            "POST",
            f"/api/v1/validations/{validation_id}/decisions",
            json=payload,
            headers={"Idempotency-Key": idempotency_key},
        )
        result = response.json()
        if not isinstance(result, dict):
            raise APIClientError("API-ul a returnat o decizie de validare invalidă.")
        return result


api_client = ChIAtratonAPIClient.from_environment()
