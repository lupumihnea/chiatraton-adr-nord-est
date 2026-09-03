from app.models.errors import ProblemDetails


def test_errors_conform_to_problem_details(client):
    response = client.get("/api/v1/projects")
    payload = response.json()

    problem = ProblemDetails.model_validate(payload)
    assert problem.status == response.status_code
    assert problem.instance == "/api/v1/projects"
    assert problem.request_id == response.headers["X-Request-Id"]
    assert response.headers["content-type"].startswith("application/problem+json")


def test_unknown_route_uses_problem_details(client):
    response = client.get("/route-that-does-not-exist")

    assert response.status_code == 404
    assert ProblemDetails.model_validate(response.json()).code == "resource_not_found"
