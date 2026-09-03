"""Small OpenAPI adjustments required by the source contract."""

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.models.domain import DocumentUpload
from app.models.errors import FieldError, ProblemDetails


def _remove_null_defaults(value: Any) -> None:
    if isinstance(value, dict):
        if value.get("default", ...) is None:
            value.pop("default")
        for child in value.values():
            _remove_null_defaults(child)
    elif isinstance(value, list):
        for child in value:
            _remove_null_defaults(child)


def install_openapi_factory(app: FastAPI) -> None:
    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            openapi_version="3.1.0",
        )
        schema["jsonSchemaDialect"] = "https://json-schema.org/draft/2020-12/schema"
        schema["servers"] = [
            {
                "url": "/",
                "description": "Originea mediului în care este publicat API-ul.",
            }
        ]
        schema["security"] = [{"bearerAuth": []}]
        schema["paths"]["/health"]["get"]["security"] = []
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        problem_schema = ProblemDetails.model_json_schema(
            by_alias=True, ref_template="#/components/schemas/{model}"
        )
        definitions = problem_schema.pop("$defs", {})
        components.update(definitions)
        components["FieldError"] = FieldError.model_json_schema(by_alias=True)
        components["ProblemDetails"] = problem_schema
        components["DocumentUpload"] = DocumentUpload.model_json_schema(by_alias=True)
        schema["paths"]["/api/v1/projects/{projectId}/documents"]["post"]["requestBody"]["content"][
            "multipart/form-data"
        ]["schema"] = {"$ref": "#/components/schemas/DocumentUpload"}
        schema["paths"]["/api/v1/analysis-jobs/{jobId}"]["get"]["responses"].pop("422", None)
        schema["paths"]["/api/v1/documents/{documentId}/content"]["get"]["responses"]["200"][
            "content"
        ].pop("application/json", None)
        _remove_null_defaults(schema)
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
