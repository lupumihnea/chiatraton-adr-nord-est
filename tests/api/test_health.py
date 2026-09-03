def test_health_returns_200(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "chiatraton-api",
        "version": "1.0.0",
    }
    assert response.headers["X-Request-Id"].startswith("req_")
