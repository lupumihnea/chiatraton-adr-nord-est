"""Shared test fixtures: synthetic FastAPI client plus the legacy sys.path bootstrap."""

import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_JWT_SECRET = "synthetic-test-secret-with-sufficient-entropy"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment="test",
        jwt_secret=SecretStr(TEST_JWT_SECRET),
        docs_enabled=True,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings), raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def auth_headers() -> dict[str, str]:
    now = datetime.now(UTC)
    token = jwt.encode(
        {"sub": "synthetic-user", "iat": now, "exp": now + timedelta(minutes=10)},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}
