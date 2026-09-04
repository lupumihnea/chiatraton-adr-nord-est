"""FastAPI application factory and dependency composition root."""

import logging
from collections.abc import Iterable

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
from app.services.ports import CriterionExtractor, ReportAnalyzer
from app.services.storage import InMemoryDocumentStorage


def _local_application_service(
    settings: Settings,
    *,
    criterion_extractor: CriterionExtractor | None,
    report_analyzer: ReportAnalyzer | None,
) -> DefaultApplicationService:
    """Compose development/demo adapters without crossing architectural boundaries."""

    if settings.repository_backend != "memory":
        raise ValueError("An external repository adapter must be injected at the composition root")
    if settings.document_storage_backend != "memory":
        raise ValueError(
            "An external document-storage adapter must be injected at the composition root"
        )
    if settings.job_runner_backend != "local":
        raise ValueError("An external job-runner adapter must be injected at the composition root")
    if settings.criterion_extractor_backend == "external" and criterion_extractor is None:
        raise ValueError("An external CriterionExtractor must be injected at the composition root")
    if settings.report_analyzer_backend == "external" and report_analyzer is None:
        raise ValueError("An external ReportAnalyzer must be injected at the composition root")

    storage = InMemoryDocumentStorage()
    runner = LocalJobRunner()

    qwen_adapter = None
    need_qwen = (
        criterion_extractor is None and settings.criterion_extractor_backend == "qwen"
    ) or (
        report_analyzer is None and settings.report_analyzer_backend == "qwen"
    )
    if need_qwen:
        # Import lazily: normal API/UI tests and fake-mode development do not
        # require the heavy semantic-retrieval dependencies.
        from AI.qwen_adapter import QwenAIAdapter

        qwen_adapter = QwenAIAdapter(
            content_loader=storage.get,
            model=settings.ai_model_name,
            base_url=settings.ai_base_url,
            api_key=settings.ai_api_key.get_secret_value(),
            timeout_seconds=settings.ai_timeout_seconds,
            contract_version=settings.ai_contract_version,
            embedding_model=settings.ai_embedding_model,
            app_url=settings.ai_app_url,
            app_name=settings.ai_app_name,
            reviewer_model=settings.ai_reviewer_model_name,
        )

    if criterion_extractor is None:
        if settings.criterion_extractor_backend == "fake":
            criterion_extractor = DeterministicFakeCriterionExtractor()
        elif settings.criterion_extractor_backend == "qwen":
            criterion_extractor = qwen_adapter
    if report_analyzer is None:
        if settings.report_analyzer_backend == "fake":
            report_analyzer = DeterministicFakeReportAnalyzer()
        elif settings.report_analyzer_backend == "qwen":
            report_analyzer = qwen_adapter

    if criterion_extractor is None or report_analyzer is None:
        raise ValueError("AI adapters could not be composed")

    return DefaultApplicationService(
        unit_of_work_factory=InMemoryUnitOfWorkFactory(),
        document_storage=storage,
        criterion_extractor=criterion_extractor,
        report_analyzer=report_analyzer,
        job_runner=runner,
        cursor_codec=CursorCodec(settings.jwt_secret.get_secret_value()),
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
