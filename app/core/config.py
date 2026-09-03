from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEVELOPMENT_JWT_SECRET = "development-only-secret-change-me"


class Settings(BaseSettings):
    """Runtime configuration loaded from CHIATRATON_* environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="CHIATRATON_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "ChIAtraton HTTP API"
    app_version: str = "1.0.0"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    docs_enabled: bool = True

    jwt_secret: SecretStr = SecretStr(DEVELOPMENT_JWT_SECRET)
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_issuer: str | None = None
    jwt_audience: str | None = None
    jwt_leeway_seconds: int = Field(default=30, ge=0, le=300)
    idempotency_backend: Literal["memory", "external"] = "memory"
    idempotency_ttl_seconds: int = Field(default=3600, ge=1, le=86_400)
    idempotency_max_entries: int = Field(default=10_000, ge=1, le=1_000_000)
    repository_backend: Literal["memory", "external"] = "memory"
    document_storage_backend: Literal["memory", "external"] = "memory"
    criterion_extractor_backend: Literal["fake", "openrouter", "external"] = "fake"
    report_analyzer_backend: Literal["fake", "openrouter", "external"] = "fake"
    job_runner_backend: Literal["local", "external"] = "local"

    openrouter_api_key: SecretStr = SecretStr("")
    openrouter_model: str = "qwen/qwen3-235b-a22b-2507"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_timeout_seconds: float = Field(default=120.0, ge=1.0, le=600.0)

    @model_validator(mode="after")
    def reject_development_secret_in_production(self) -> Settings:
        if (
            self.environment == "production"
            and self.jwt_secret.get_secret_value() == DEVELOPMENT_JWT_SECRET
        ):
            raise ValueError("CHIATRATON_JWT_SECRET must be configured in production")
        if self.environment == "production" and self.idempotency_backend == "memory":
            raise ValueError("CHIATRATON_IDEMPOTENCY_BACKEND must be external in production")
        local_adapters = {
            "CHIATRATON_REPOSITORY_BACKEND": self.repository_backend == "memory",
            "CHIATRATON_DOCUMENT_STORAGE_BACKEND": self.document_storage_backend == "memory",
            "CHIATRATON_CRITERION_EXTRACTOR_BACKEND": self.criterion_extractor_backend == "fake",
            "CHIATRATON_REPORT_ANALYZER_BACKEND": self.report_analyzer_backend == "fake",
            "CHIATRATON_JOB_RUNNER_BACKEND": self.job_runner_backend == "local",
        }
        if self.environment == "production":
            invalid = [name for name, selected in local_adapters.items() if selected]
            if invalid:
                raise ValueError(
                    "Production requires external adapters; local adapter selected by "
                    + ", ".join(invalid)
                )
        uses_openrouter = "openrouter" in (
            self.criterion_extractor_backend,
            self.report_analyzer_backend,
        )
        if uses_openrouter and not self.openrouter_api_key.get_secret_value().strip():
            raise ValueError(
                "CHIATRATON_OPENROUTER_API_KEY must be set when the openrouter "
                "backend is selected for CHIATRATON_CRITERION_EXTRACTOR_BACKEND "
                "or CHIATRATON_REPORT_ANALYZER_BACKEND"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
