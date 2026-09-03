"""Generate a short-lived Bearer JWT for local development only."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", default="synthetic-demo-user")
    parser.add_argument("--minutes", type=int, default=60, choices=range(1, 481))
    arguments = parser.parse_args()
    settings = Settings()
    if settings.environment == "production":
        raise SystemExit("Development tokens cannot be generated in production.")
    now = datetime.now(UTC)
    claims: dict[str, object] = {
        "sub": arguments.subject,
        "iat": now,
        "exp": now + timedelta(minutes=arguments.minutes),
    }
    if settings.jwt_issuer is not None:
        claims["iss"] = settings.jwt_issuer
    if settings.jwt_audience is not None:
        claims["aud"] = settings.jwt_audience
    token = jwt.encode(
        claims,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    print(token)


if __name__ == "__main__":
    main()
