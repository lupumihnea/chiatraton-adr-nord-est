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


def test_stub_is_reached_with_authentication_and_idempotency(client, auth_headers):
    response = client.post(
        "/api/v1/projects",
        headers={**auth_headers, "Idempotency-Key": "synthetic-create-project-1"},
        json={
            "name": "Synthetic monitoring project",
            "completionDate": "2030-12-31",
            "monitoringEndDate": "2033-12-31",
        },
    )

    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert "createProject" in response.json()["detail"]
