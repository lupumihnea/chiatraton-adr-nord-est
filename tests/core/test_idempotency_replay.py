from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.errors import ProblemDetails
from tests.support.idempotency_app import TEST_SECRET, IdempotencyHarness


def _authorization(subject: str, key: str) -> dict[str, str]:
    now = datetime.now(UTC)
    token = jwt.encode(
        {"sub": subject, "iat": now, "exp": now + timedelta(minutes=5)},
        TEST_SECRET,
        algorithm="HS256",
    )
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Idempotency-Key": key,
    }


def _client() -> tuple[TestClient, IdempotencyHarness]:
    harness = IdempotencyHarness()
    settings = Settings(environment="test", jwt_secret=TEST_SECRET)
    client = TestClient(
        create_app(settings, extra_routers=[harness.router]),
        raise_server_exceptions=False,
    )
    return client, harness


def test_same_key_and_semantic_json_replays_original_response():
    client, harness = _client()
    headers = _authorization("user-a", "same-request")
    with client:
        original = client.post(
            "/__test__/idempotency/project-a",
            headers=headers,
            content=b'{"value":"one","extra":1}',
        )
        replay = client.post(
            "/__test__/idempotency/project-a",
            headers=headers,
            content=b'{"extra":1,"value":"one"}',
        )

    assert original.status_code == 201
    assert replay.status_code == 201
    assert replay.json() == original.json()
    assert original.headers.get("Idempotency-Replayed") is None
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.headers["Location"] == original.headers["Location"]
    assert harness.executions[("user-a", "project-a")] == 1


def test_same_key_with_different_body_returns_problem_details_conflict():
    client, harness = _client()
    headers = _authorization("user-a", "conflicting-request")
    with client:
        first = client.post(
            "/__test__/idempotency/project-a", headers=headers, json={"value": "one"}
        )
        conflict = client.post(
            "/__test__/idempotency/project-a", headers=headers, json={"value": "two"}
        )

    assert first.status_code == 201
    assert conflict.status_code == 409
    assert conflict.headers["content-type"].startswith("application/problem+json")
    assert ProblemDetails.model_validate(conflict.json()).code == "idempotency_conflict"
    assert harness.executions[("user-a", "project-a")] == 1


def test_key_is_isolated_between_users():
    client, harness = _client()
    with client:
        first = client.post(
            "/__test__/idempotency/project-a",
            headers=_authorization("user-a", "shared-key"),
            json={"value": "same"},
        )
        second = client.post(
            "/__test__/idempotency/project-a",
            headers=_authorization("user-b", "shared-key"),
            json={"value": "same"},
        )

    assert first.status_code == second.status_code == 201
    assert first.headers.get("Idempotency-Replayed") is None
    assert second.headers.get("Idempotency-Replayed") is None
    assert harness.executions[("user-a", "project-a")] == 1
    assert harness.executions[("user-b", "project-a")] == 1


def test_key_is_isolated_between_routes_and_resources():
    client, harness = _client()
    headers = _authorization("user-a", "resource-key")
    with client:
        first = client.post(
            "/__test__/idempotency/project-a", headers=headers, json={"value": "same"}
        )
        second = client.post(
            "/__test__/idempotency/project-b", headers=headers, json={"value": "same"}
        )
        alternate = client.post(
            "/__test__/idempotency-alternate/project-a",
            headers=headers,
            json={"value": "same"},
        )

    assert first.status_code == second.status_code == alternate.status_code == 201
    assert harness.executions[("user-a", "project-a")] == 1
    assert harness.executions[("user-a", "project-b")] == 1
    assert harness.executions[("user-a", "alternate/project-a")] == 1


def test_5xx_responses_are_not_stored():
    client, harness = _client()
    headers = _authorization("user-a", "failing-request")
    with client:
        first = client.post(
            "/__test__/idempotency/project-a", headers=headers, json={"force5xx": True}
        )
        second = client.post(
            "/__test__/idempotency/project-a", headers=headers, json={"force5xx": True}
        )

    assert first.status_code == second.status_code == 500
    assert first.headers.get("Idempotency-Replayed") is None
    assert second.headers.get("Idempotency-Replayed") is None
    assert harness.executions[("user-a", "project-a")] == 2


def test_concurrent_same_request_executes_once():
    client, harness = _client()
    headers = _authorization("user-a", "concurrent-request")

    def send_request() -> tuple[int, str | None]:
        response = client.post(
            "/__test__/idempotency/project-a",
            headers=headers,
            json={"value": "same", "delay": True},
        )
        return response.status_code, response.headers.get("Idempotency-Replayed")

    with client, ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: send_request(), range(8)))

    assert all(status_code == 201 for status_code, _ in results)
    assert sum(replayed == "true" for _, replayed in results) == 7
    assert harness.executions[("user-a", "project-a")] == 1
