"""Contract-focused tests for the shared NiceGUI HTTP client."""

from __future__ import annotations

import json

import httpx
import pytest

from Interface.api_client import (
    APIConfigurationError,
    APIProblemError,
    ChIAtratonAPIClient,
    IdempotencyKeyManager,
    json_fingerprint,
    upload_fingerprint,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_list_projects_uses_bearer_auth_and_contract_query() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"items": [], "nextCursor": None})

    client = ChIAtratonAPIClient(
        base_url="http://api.test",
        bearer_token="synthetic-token",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await client.list_projects(limit=25, cursor="opaque-cursor")
    finally:
        await client.close()

    assert result == {"items": [], "nextCursor": None}
    assert len(requests) == 1
    request = requests[0]
    assert request.url == "http://api.test/api/v1/projects?limit=25&cursor=opaque-cursor"
    assert request.headers["Authorization"] == "Bearer synthetic-token"


@pytest.mark.anyio
async def test_create_project_sends_exact_payload_and_idempotency_key() -> None:
    payload = {
        "name": "Proiect sintetic UI",
        "completionDate": "2030-06-30",
        "monitoringEndDate": "2033-06-30",
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/projects"
        assert request.headers["Idempotency-Key"] == "ui-project-key"
        assert json.loads(await request.aread()) == payload
        return httpx.Response(201, json={"id": "00000000-0000-4000-8000-000000000001"})

    client = ChIAtratonAPIClient(
        base_url="http://api.test",
        bearer_token="synthetic-token",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await client.create_project(payload, idempotency_key="ui-project-key")
    finally:
        await client.close()

    assert result["id"] == "00000000-0000-4000-8000-000000000001"
    assert set(payload) == {"name", "completionDate", "monitoringEndDate"}


@pytest.mark.anyio
async def test_upload_uses_multipart_jwt_and_idempotency_key() -> None:
    body = b"%PDF-1.4\nSynthetic UI document\n%%EOF\n"

    async def handler(request: httpx.Request) -> httpx.Response:
        raw = await request.aread()
        assert request.method == "POST"
        assert request.url.path.endswith(
            "/projects/00000000-0000-4000-8000-000000000001/documents"
        )
        assert request.headers["Authorization"] == "Bearer synthetic-token"
        assert request.headers["Idempotency-Key"] == "ui-upload-key"
        assert request.headers["Content-Type"].startswith("multipart/form-data;")
        assert b'name="file"' in raw
        assert b'filename="synthetic.pdf"' in raw
        assert b'name="displayName"' in raw
        assert b"Document sintetic" in raw
        assert body in raw
        return httpx.Response(201, json={"id": "00000000-0000-4000-8000-000000000002"})

    client = ChIAtratonAPIClient(
        base_url="http://api.test",
        bearer_token="synthetic-token",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await client.upload_document(
            "00000000-0000-4000-8000-000000000001",
            filename="synthetic.pdf",
            content=body,
            content_type="application/pdf",
            display_name="Document sintetic",
            idempotency_key="ui-upload-key",
        )
    finally:
        await client.close()

    assert result["id"] == "00000000-0000-4000-8000-000000000002"


@pytest.mark.anyio
async def test_problem_details_is_preserved_for_ui_error_display() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            422,
            headers={"Content-Type": "application/problem+json"},
            json={
                "type": "https://example.test/problems/validation-error",
                "title": "Request validation failed",
                "status": 422,
                "detail": "monitoringEndDate must be on or after completionDate",
                "instance": "/api/v1/projects",
                "code": "validation_error",
                "requestId": "synthetic-request-id",
                "errors": [
                    {
                        "field": "monitoringEndDate",
                        "code": "value_error",
                        "message": "Invalid date range",
                    }
                ],
            },
        )

    client = ChIAtratonAPIClient(
        base_url="http://api.test",
        bearer_token="synthetic-token",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(APIProblemError) as caught:
        await client.create_project(
            {
                "name": "Sintetic",
                "completionDate": "2033-01-01",
                "monitoringEndDate": "2030-01-01",
            },
            idempotency_key="problem-key",
        )
    await client.close()

    assert caught.value.problem.status == 422
    assert caught.value.problem.code == "validation_error"
    assert caught.value.problem.request_id == "synthetic-request-id"
    assert caught.value.problem.errors[0]["field"] == "monitoringEndDate"


@pytest.mark.anyio
async def test_missing_bearer_token_is_rejected_before_transport() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Unexpected request: {request.url}")

    client = ChIAtratonAPIClient(
        base_url="http://api.test",
        bearer_token="",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(APIConfigurationError):
        await client.list_projects()
    await client.close()


@pytest.mark.anyio
async def test_client_configuration_is_loaded_from_ui_environment(monkeypatch) -> None:
    monkeypatch.setenv("CHIATRATON_API_BASE_URL", "http://configured-api.test/root/")
    monkeypatch.setenv("CHIATRATON_UI_BEARER_TOKEN", "configured-token")
    client = ChIAtratonAPIClient.from_environment()
    try:
        assert client.base_url == "http://configured-api.test/root"
        assert client._authorization_headers() == {  # noqa: SLF001
            "Authorization": "Bearer configured-token"
        }
    finally:
        await client.close()


def test_idempotency_key_stays_stable_only_for_the_same_pending_payload() -> None:
    manager = IdempotencyKeyManager()
    first_payload = json_fingerprint({"name": "A"})
    changed_payload = json_fingerprint({"name": "B"})

    first_key = manager.key_for("create", first_payload)
    assert manager.key_for("create", first_payload) == first_key
    assert manager.key_for("create", changed_payload) != first_key

    changed_key = manager.key_for("create", changed_payload)
    manager.mark_succeeded("create", changed_payload)
    assert manager.key_for("create", changed_payload) != changed_key


def test_upload_fingerprint_changes_with_content_or_display_name() -> None:
    common = {
        "project_id": "00000000-0000-4000-8000-000000000001",
        "filename": "synthetic.pdf",
        "content_type": "application/pdf",
    }
    first = upload_fingerprint(**common, content=b"one", display_name="Source")
    retry = upload_fingerprint(**common, content=b"one", display_name="Source")
    changed_content = upload_fingerprint(**common, content=b"two", display_name="Source")
    changed_name = upload_fingerprint(**common, content=b"one", display_name="Report")

    assert retry == first
    assert changed_content != first
    assert changed_name != first


@pytest.mark.anyio
async def test_progress_report_client_uses_existing_report_contract() -> None:
    seen: list[tuple[str, str, dict]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(await request.aread()) if request.method == "POST" else {}
        seen.append((request.method, request.url.path, payload))
        if request.url.path.endswith("/reports"):
            return httpx.Response(201, json={"id": "00000000-0000-4000-8000-000000000010"})
        if request.url.path.endswith("/analysis-jobs"):
            return httpx.Response(202, json={"id": "00000000-0000-4000-8000-000000000011"})
        raise AssertionError(f"Unexpected request: {request.url}")

    client = ChIAtratonAPIClient(
        base_url="http://api.test",
        bearer_token="synthetic-token",
        transport=httpx.MockTransport(handler),
    )
    try:
        report = await client.create_project_report(
            "00000000-0000-4000-8000-000000000001",
            period_start="2030-01-01",
            period_end="2030-03-31",
            document_id="00000000-0000-4000-8000-000000000002",
            idempotency_key="report-key",
        )
        job = await client.create_report_analysis_job(
            report["id"],
            idempotency_key="analysis-key",
        )
    finally:
        await client.close()

    assert job["id"] == "00000000-0000-4000-8000-000000000011"
    assert seen[0] == (
        "POST",
        "/api/v1/projects/00000000-0000-4000-8000-000000000001/reports",
        {
            "reportType": "implementation_progress",
            "periodStart": "2030-01-01",
            "periodEnd": "2030-03-31",
            "documents": [
                {
                    "documentId": "00000000-0000-4000-8000-000000000002",
                    "role": "main_report",
                }
            ],
        },
    )
    assert seen[1] == (
        "POST",
        "/api/v1/reports/00000000-0000-4000-8000-000000000010/analysis-jobs",
        {"projectDocumentIds": [], "previousReportIds": []},
    )


@pytest.mark.anyio
async def test_validation_decision_client_uses_existing_contract() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == (
            "/api/v1/validations/00000000-0000-4000-8000-000000000020/decisions"
        )
        assert request.headers["Idempotency-Key"] == "decision-key"
        assert json.loads(await request.aread()) == {
            "action": "correct",
            "validationRevision": 2,
            "finalOutcome": "compliant",
            "comment": "Corecție sintetică verificată de utilizator.",
        }
        return httpx.Response(
            201,
            json={
                "id": "00000000-0000-4000-8000-000000000021",
                "action": "correct",
            },
        )

    client = ChIAtratonAPIClient(
        base_url="http://api.test",
        bearer_token="synthetic-token",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await client.create_validation_decision(
            "00000000-0000-4000-8000-000000000020",
            validation_revision=2,
            action="correct",
            final_outcome="compliant",
            comment="Corecție sintetică verificată de utilizator.",
            idempotency_key="decision-key",
        )
    finally:
        await client.close()

    assert result["action"] == "correct"
