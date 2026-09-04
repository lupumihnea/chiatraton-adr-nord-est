def _headers(auth_headers: dict[str, str], key: str) -> dict[str, str]:
    return {**auth_headers, "Idempotency-Key": key}


def test_document_question_endpoint_abstains_without_fake_evidence(client, auth_headers) -> None:
    project_response = client.post(
        "/api/v1/projects",
        headers=_headers(auth_headers, "qa-project"),
        json={"name": "QA project"},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]
    upload_response = client.post(
        f"/api/v1/projects/{project_id}/documents",
        headers=_headers(auth_headers, "qa-document"),
        files={"file": ("source.pdf", b"Synthetic PDF", "application/pdf")},
    )
    assert upload_response.status_code == 201

    response = client.post(
        f"/api/v1/projects/{project_id}/document-questions",
        headers=_headers(auth_headers, "qa-question"),
        json={"question": "Care este contribuția proprie?", "documentIds": []},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "not_found",
        "answer": "Nu am găsit informația solicitată în documentele selectate.",
        "matches": [],
    }
