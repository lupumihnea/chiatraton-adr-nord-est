from pathlib import Path

import yaml
from openapi_spec_validator import validate

from app.main import create_app

ROOT = Path(__file__).resolve().parents[2]
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _source_contract():
    return yaml.safe_load((ROOT / "contracts" / "openapi.yaml").read_text(encoding="utf-8"))


def _success_status(operation):
    return next(code for code in operation["responses"] if code.startswith("2"))


def test_source_and_generated_openapi_are_valid(settings):
    source = _source_contract()
    generated = create_app(settings).openapi()

    validate(source)
    validate(generated)


def test_paths_methods_operation_ids_and_success_statuses_match_contract(settings):
    source = _source_contract()
    generated = create_app(settings).openapi()

    assert set(generated["paths"]) == set(source["paths"])
    for path, source_path in source["paths"].items():
        expected_methods = HTTP_METHODS.intersection(source_path)
        actual_methods = HTTP_METHODS.intersection(generated["paths"][path])
        assert actual_methods == expected_methods
        for method in expected_methods:
            expected = source_path[method]
            actual = generated["paths"][path][method]
            assert actual["operationId"] == expected["operationId"]
            assert set(actual["responses"]) == set(expected["responses"])
            assert _success_status(actual) == _success_status(expected)
            if "requestBody" in expected:
                expected_content = expected["requestBody"]["content"]
                actual_content = actual["requestBody"]["content"]
                assert set(actual_content) == set(expected_content)
                media_type = next(iter(expected_content))
                assert (
                    actual_content[media_type]["schema"] == expected_content[media_type]["schema"]
                )


def test_all_post_operations_require_idempotency_and_all_api_routes_require_jwt(settings):
    generated = create_app(settings).openapi()

    for path, path_item in generated["paths"].items():
        for method in HTTP_METHODS.intersection(path_item):
            operation = path_item[method]
            if method == "post":
                parameters = operation.get("parameters", [])
                key = next(item for item in parameters if item.get("name") == "Idempotency-Key")
                assert key["in"] == "header"
                assert key["required"] is True
            if path.startswith("/api/v1"):
                assert {"bearerAuth": []} in operation["security"]

    assert generated["paths"]["/health"]["get"]["security"] == []


def test_response_models_and_problem_media_type_match_contract(settings):
    source = _source_contract()
    generated = create_app(settings).openapi()

    for path, source_path in source["paths"].items():
        for method in HTTP_METHODS.intersection(source_path):
            source_operation = source_path[method]
            generated_operation = generated["paths"][path][method]
            status = _success_status(source_operation)
            source_content = source_operation["responses"][status].get("content", {})
            generated_content = generated_operation["responses"][status].get("content", {})
            expected_success_headers = set(source_operation["responses"][status].get("headers", {}))
            assert (
                set(generated_operation["responses"][status].get("headers", {}))
                == expected_success_headers
            )
            if "application/json" in source_content:
                assert generated_content["application/json"]["schema"].get(
                    "$ref"
                ) == source_content["application/json"]["schema"].get("$ref")
            for error_status in set(source_operation["responses"]).intersection(
                generated_operation["responses"]
            ):
                if error_status.startswith(("4", "5")):
                    assert (
                        "X-Request-Id" in generated_operation["responses"][error_status]["headers"]
                    )
                    assert (
                        "application/problem+json"
                        in generated_operation["responses"][error_status]["content"]
                    )
