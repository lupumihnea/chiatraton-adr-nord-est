def test_missing_idempotency_key_is_rejected(client, auth_headers):
    response = client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={
            "name": "Synthetic monitoring project",
            "completionDate": "2030-12-31",
            "monitoringEndDate": "2033-12-31",
        },
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "validation_error"
    assert any(error["field"] == "header.Idempotency-Key" for error in body["errors"])


def test_project_creation_is_functional_with_authentication_and_idempotency(client, auth_headers):
    response = client.post(
        "/api/v1/projects",
        headers={**auth_headers, "Idempotency-Key": "synthetic-create-project-1"},
        json={
            "name": "Synthetic monitoring project",
            "completionDate": "2030-12-31",
            "monitoringEndDate": "2033-12-31",
        },
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Synthetic monitoring project"
    assert response.headers["Location"].endswith(response.json()["id"])


def test_real_operation_replays_and_conflicts(client, auth_headers):
    headers = {**auth_headers, "Idempotency-Key": "synthetic-real-replay"}
    payload = {
        "name": "Synthetic replay project",
        "completionDate": "2030-12-31",
        "monitoringEndDate": "2033-12-31",
    }

    original = client.post("/api/v1/projects", headers=headers, json=payload)
    replay = client.post("/api/v1/projects", headers=headers, json=payload)
    conflict = client.post(
        "/api/v1/projects", headers=headers, json={**payload, "name": "Different payload"}
    )

    assert original.status_code == replay.status_code == 201
    assert replay.json() == original.json()
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.headers["Location"] == original.headers["Location"]
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_conflict"
