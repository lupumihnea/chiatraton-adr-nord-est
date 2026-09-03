"""FastAPI application factory and dependency composition root."""

import logging
from collections.abc import Iterable

import httpx
from fastapi import APIRouter, FastAPI

from app.api import api_router
from app.core.config import Settings, get_settings
from app.core.cursors import CursorCodec
from app.core.handlers import register_exception_handlers
from app.core.idempotency_memory import InMemoryIdempotencyStore
from app.core.idempotency_middleware import IdempotencyMiddleware
from app.core.middleware import request_context_middleware
from app.core.openapi import install_openapi_factory
from app.repositories.memory import InMemoryUnitOfWorkFactory
from app.services.default import DefaultApplicationService
from app.services.fake_ai import (
    DeterministicFakeCriterionExtractor,
    DeterministicFakeReportAnalyzer,
)
from app.services.idempotency import IdempotencyStore
from app.services.interfaces import ApplicationService
from app.services.job_runner import LocalJobRunner
from app.services.openrouter_ai import OpenRouterCriterionExtractor, OpenRouterReportAnalyzer
from app.services.ports import CriterionExtractor, ReportAnalyzer
from app.services.storage import InMemoryDocumentStorage

_LOCAL_EXTRACTOR_BACKENDS = {"fake", "openrouter"}
_LOCAL_ANALYZER_BACKENDS = {"fake", "openrouter"}


def _local_application_service(
    settings: Settings,
    *,
    criterion_extractor: CriterionExtractor | None,
    report_analyzer: ReportAnalyzer | None,
) -> DefaultApplicationService:
    if settings.repository_backend != "memory":
        raise ValueError("External repository adapters must be injected at the composition root")
    if settings.document_storage_backend != "memory":
        raise ValueError(
            "External document storage adapters must be injected at the composition root"
        )
    if settings.criterion_extractor_backend not in _LOCAL_EXTRACTOR_BACKENDS:
        raise ValueError(
            "External criterion extractor adapters must be injected at the composition root"
        )
    if settings.report_analyzer_backend not in _LOCAL_ANALYZER_BACKENDS:
        raise ValueError(
            "External report analyzer adapters must be injected at the composition root"
        )
    if settings.job_runner_backend != "local":
        raise ValueError("External job runner adapters must be injected at the composition root")

    runner = LocalJobRunner()
    document_storage = InMemoryDocumentStorage()

    openrouter_client: httpx.AsyncClient | None = None

    def _openrouter_client() -> httpx.AsyncClient:
        nonlocal openrouter_client
        if openrouter_client is None:
            openrouter_client = httpx.AsyncClient()
        return openrouter_client

    if criterion_extractor is None:
        if settings.criterion_extractor_backend == "openrouter":
            criterion_extractor = OpenRouterCriterionExtractor(
                document_storage=document_storage,
                api_key=settings.openrouter_api_key.get_secret_value(),
                model=settings.openrouter_model,
                base_url=settings.openrouter_base_url,
                client=_openrouter_client(),
                timeout_seconds=settings.openrouter_timeout_seconds,
            )
        else:
            criterion_extractor = DeterministicFakeCriterionExtractor()

    if report_analyzer is None:
        if settings.report_analyzer_backend == "openrouter":
            report_analyzer = OpenRouterReportAnalyzer(
                document_storage=document_storage,
                api_key=settings.openrouter_api_key.get_secret_value(),
                model=settings.openrouter_model,
                base_url=settings.openrouter_base_url,
                client=_openrouter_client(),
                timeout_seconds=settings.openrouter_timeout_seconds,
            )
        else:
            report_analyzer = DeterministicFakeReportAnalyzer()

    return DefaultApplicationService(
        unit_of_work_factory=InMemoryUnitOfWorkFactory(),
        document_storage=document_storage,
        criterion_extractor=criterion_extractor,
        report_analyzer=report_analyzer,
        job_runner=runner,
        cursor_codec=CursorCodec(settings.jwt_secret.get_secret_value()),
        extra_shutdown_hooks=(openrouter_client.aclose,) if openrouter_client is not None else (),
    )


def create_app(
    settings: Settings | None = None,
    *,
    idempotency_store: IdempotencyStore | None = None,
    application_service: ApplicationService | None = None,
    criterion_extractor: CriterionExtractor | None = None,
    report_analyzer: ReportAnalyzer | None = None,
    extra_routers: Iterable[APIRouter] = (),
) -> FastAPI:
    runtime_settings = settings or get_settings()
    docs_url = "/docs" if runtime_settings.docs_enabled else None
    redoc_url = "/redoc" if runtime_settings.docs_enabled else None
    openapi_url = "/openapi.json" if runtime_settings.docs_enabled else None

    application = FastAPI(
        title=runtime_settings.app_name,
        version=runtime_settings.app_version,
        description=(
            "Contract-first API for the ChIAtraton AI verification workspace. "
            "It does not replace or operate MyADR/MySMIS."
        ),
        debug=runtime_settings.debug,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        openapi_version="3.1.0",
    )
    application.state.settings = runtime_settings
    application.state.logger = logging.getLogger("chiatraton.api")
    if idempotency_store is None:
        if runtime_settings.idempotency_backend != "memory":
            raise ValueError("An external IdempotencyStore adapter must be injected")
        idempotency_store = InMemoryIdempotencyStore(
            ttl_seconds=runtime_settings.idempotency_ttl_seconds,
            max_entries=runtime_settings.idempotency_max_entries,
        )
    if application_service is None:
        if runtime_settings.environment == "production":
            raise ValueError("An external ApplicationService must be injected in production")
        application_service = _local_application_service(
            runtime_settings,
            criterion_extractor=criterion_extractor,
            report_analyzer=report_analyzer,
        )
    application.state.idempotency_store = idempotency_store
    application.state.application_service = application_service
    application.add_middleware(IdempotencyMiddleware, store=idempotency_store)
    application.middleware("http")(request_context_middleware)
    register_exception_handlers(application)
    application.include_router(api_router)
    for router in extra_routers:
        application.include_router(router)
    install_openapi_factory(application)

    close = getattr(application_service, "close", None)
    if close is not None:
        application.router.add_event_handler("shutdown", close)
    return application


app = create_app()
