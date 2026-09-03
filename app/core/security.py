"""Bearer JWT authentication dependency."""

from typing import Annotated, Any

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import Field

from app.core.config import Settings
from app.core.exceptions import ProblemException
from app.models.base import APIModel


class CurrentUser(APIModel):
    subject: str = Field(min_length=1, max_length=255)
    claims: dict[str, Any]


bearer_scheme = HTTPBearer(
    auto_error=False,
    bearerFormat="JWT",
    scheme_name="bearerAuth",
    description="Tokenul identifică utilizatorul tehnic pentru audit.",
)


def _authentication_error(detail: str) -> ProblemException:
    return ProblemException(
        status=401,
        code="authentication_required",
        title="Authentication required",
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def decode_bearer_token(token: str, settings: Settings) -> CurrentUser:
    options = {
        "require": ["exp", "sub"],
        "verify_aud": settings.jwt_audience is not None,
        "verify_iss": settings.jwt_issuer is not None,
    }
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            leeway=settings.jwt_leeway_seconds,
            options=options,
        )
    except jwt.InvalidTokenError as exc:
        raise _authentication_error("The Bearer JWT is invalid or expired.") from exc

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise _authentication_error("The Bearer JWT subject is invalid.")
    return CurrentUser(subject=subject, claims=claims)


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _authentication_error("A valid Bearer JWT is required.")
    settings: Settings = request.app.state.settings
    return decode_bearer_token(credentials.credentials, settings)
