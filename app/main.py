"""FastAPI application factory."""

import logging
from collections.abc import Iterable

from fastapi import APIRouter, FastAPI

from app.api import api_router
from app.core.config import Settings, get_settings
from app.core.handlers import register_exception_handlers
from app.core.idempotency_memory import InMemoryIdempotencyStore
from app.core.idempotency_middleware import IdempotencyMiddleware
from app.core.middleware import request_context_middleware
from app.core.openapi import install_openapi_factory
from app.services.idempotency import IdempotencyStore


def create_app(
    settings: Settings | None = None,
    *,
    idempotency_store: IdempotencyStore | None = None,
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
    application.state.idempotency_store = idempotency_store
    application.add_middleware(IdempotencyMiddleware, store=idempotency_store)
    application.middleware("http")(request_context_middleware)
    register_exception_handlers(application)
    application.include_router(api_router)
    for router in extra_routers:
        application.include_router(router)
    install_openapi_factory(application)
    return application


app = create_app()
