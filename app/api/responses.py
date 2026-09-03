"""OpenAPI metadata for RFC 9457 responses."""

from typing import Any

DESCRIPTIONS = {
    401: "Autentificarea lipsește sau tokenul este invalid.",
    404: "Resursa nu există sau nu este vizibilă utilizatorului.",
    409: "Operația intră în conflict cu starea curentă.",
    413: "Fișierul depășește limita acceptată.",
    415: "Tipul fișierului nu este acceptat.",
    422: "Cererea nu respectă schema sau regulile de business.",
    429: "Limita de cereri a fost depășită.",
    500: "Eroare internă neașteptată.",
    503: "Serviciul AI nu este disponibil.",
}

REQUEST_ID_HEADER = {
    "description": "Identificator opac pentru corelarea tehnică a cererii.",
    "schema": {"type": "string", "minLength": 1, "maxLength": 128},
}


def success_response(status_code: int, *, created: bool = False) -> dict[int, dict[str, Any]]:
    headers: dict[str, Any] = {"X-Request-Id": REQUEST_ID_HEADER}
    if created:
        headers.update(
            {
                "Location": {
                    "description": "URI-ul resursei create.",
                    "schema": {"type": "string", "format": "uri-reference"},
                },
                "Idempotency-Replayed": {
                    "description": "Este true numai pentru un replay idempotent.",
                    "required": False,
                    "schema": {"type": "boolean"},
                },
            }
        )
    return {status_code: {"description": "Successful Response", "headers": headers}}


def problem_responses(*status_codes: int) -> dict[int, dict[str, Any]]:
    return {
        status: {
            "description": DESCRIPTIONS[status],
            "headers": {"X-Request-Id": REQUEST_ID_HEADER},
            "content": {
                "application/problem+json": {
                    "schema": {"$ref": "#/components/schemas/ProblemDetails"}
                }
            },
        }
        for status in status_codes
    }
