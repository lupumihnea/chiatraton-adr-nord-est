def test_protected_endpoint_without_jwt_returns_401(client):
    response = client.get("/api/v1/projects")

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["code"] == "authentication_required"
