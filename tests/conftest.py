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
    # Explicit kwargs win over both a developer's local .env and any
    # environment variables already mutated by importing Interface.api_client
    # (which calls load_dotenv() at import time). Tests must stay hermetic
    # even when CHIATRATON_CRITERION_EXTRACTOR_BACKEND=qwen is set locally
    # for manual testing, or the suite would try to call OpenRouter for real.
    return Settings(
        _env_file=None,
        environment="test",
        jwt_secret=SecretStr(TEST_JWT_SECRET),
        docs_enabled=True,
        criterion_extractor_backend="fake",
        report_analyzer_backend="fake",
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
