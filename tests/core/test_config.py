import pytest
from pydantic import ValidationError

from app.core.config import DEVELOPMENT_JWT_SECRET, Settings


def test_settings_are_loaded_from_environment(monkeypatch):
    monkeypatch.setenv("CHIATRATON_APP_VERSION", "1.2.3-test")
    monkeypatch.setenv("CHIATRATON_DOCS_ENABLED", "false")

    settings = Settings(_env_file=None)

    assert settings.app_version == "1.2.3-test"
    assert settings.docs_enabled is False


def test_production_rejects_development_jwt_secret():
    with pytest.raises(ValidationError, match="CHIATRATON_JWT_SECRET"):
        Settings(
            _env_file=None,
            environment="production",
            jwt_secret=DEVELOPMENT_JWT_SECRET,
        )


def test_production_rejects_process_local_idempotency():
    with pytest.raises(ValidationError, match="CHIATRATON_IDEMPOTENCY_BACKEND"):
        Settings(
            _env_file=None,
            environment="production",
            jwt_secret="synthetic-production-secret",
            idempotency_backend="memory",
        )


def test_production_rejects_any_local_application_adapter():
    with pytest.raises(ValidationError, match="Production requires external adapters"):
        Settings(
            _env_file=None,
            environment="production",
            jwt_secret="synthetic-production-secret",
            idempotency_backend="external",
            docs_enabled=False,
        )


def test_production_accepts_only_external_adapter_configuration():
    settings = Settings(
        _env_file=None,
        environment="production",
        jwt_secret="synthetic-production-secret",
        idempotency_backend="external",
        repository_backend="external",
        document_storage_backend="external",
        criterion_extractor_backend="external",
        report_analyzer_backend="external",
        job_runner_backend="external",
        docs_enabled=False,
    )

    assert settings.docs_enabled is False
    assert settings.idempotency_backend == "external"
