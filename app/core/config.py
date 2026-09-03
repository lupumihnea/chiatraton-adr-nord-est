from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, model_validator
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
        populate_by_name=True,
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
    criterion_extractor_backend: Literal["fake", "qwen", "external"] = "fake"
    report_analyzer_backend: Literal["fake", "qwen", "external"] = "fake"
    job_runner_backend: Literal["local", "external"] = "local"

    # AIClient configuration.  Exact AI_* names come from contracts/ai-contract.md;
    # CHIATRATON_AI_* and the previous OpenRouter variable names are accepted for
    # deployment convenience without leaking them into the domain model.
    ai_provider: str = Field(
        default="qwen",
        validation_alias=AliasChoices("AI_PROVIDER", "CHIATRATON_AI_PROVIDER"),
    )
    ai_model_name: str = Field(
        default="qwen/qwen3-235b-a22b-2507",
        validation_alias=AliasChoices(
            "AI_MODEL_NAME", "CHIATRATON_AI_MODEL_NAME", "OPENROUTER_PAID_MODEL"
        ),
    )
    ai_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        validation_alias=AliasChoices(
            "AI_BASE_URL", "CHIATRATON_AI_BASE_URL", "OPENROUTER_BASE_URL"
        ),
    )
    ai_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices(
            "AI_API_KEY", "CHIATRATON_AI_API_KEY", "OPENROUTER_API_KEY"
        ),
    )
    ai_timeout_seconds: float = Field(
        default=180.0,
        ge=1.0,
        le=600.0,
        validation_alias=AliasChoices("AI_TIMEOUT_SECONDS", "CHIATRATON_AI_TIMEOUT_SECONDS"),
    )
    ai_contract_version: str = Field(
        default="1.0",
        validation_alias=AliasChoices("AI_CONTRACT_VERSION", "CHIATRATON_AI_CONTRACT_VERSION"),
    )
    ai_embedding_model: str = Field(
        default="intfloat/multilingual-e5-small",
        validation_alias=AliasChoices(
            "LOCAL_EMBEDDING_MODEL", "CHIATRATON_AI_EMBEDDING_MODEL"
        ),
    )
    ai_app_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENROUTER_APP_URL", "CHIATRATON_AI_APP_URL"),
    )
    ai_app_name: str = Field(
        default="ChIAtraton",
        validation_alias=AliasChoices("OPENROUTER_APP_NAME", "CHIATRATON_AI_APP_NAME"),
    )

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
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
