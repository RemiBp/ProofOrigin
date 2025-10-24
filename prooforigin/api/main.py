"""FastAPI application factory."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from prooforigin import tasks  # noqa: F401 - ensure tasks registered
from prooforigin.api.routers import OPTIONAL_ROUTER_ERRORS, get_router_modules
from prooforigin.core.database import init_database
from prooforigin.core.logging import setup_logging
from prooforigin.core.observability import configure_observability
from prooforigin.core.rate_limiter import setup_rate_limiting
from prooforigin.core.settings import get_settings
from prooforigin.web.router import router as web_router


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging()
    init_database()

    app = FastAPI(title=settings.app_name, version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    setup_rate_limiting(app)
    configure_observability(app)

    for name, module in get_router_modules().items():
        router = getattr(module, "router", None)
        if router is None:  # pragma: no cover - defensive guard
            logger.warning("router_module_missing_router", module=name)
            continue
        app.include_router(router)

    if OPTIONAL_ROUTER_ERRORS:
        for router_name, error in OPTIONAL_ROUTER_ERRORS.items():
            logger.warning(
                "router_skipped_optional_dependency",
                router=router_name,
                error=error,
            )

    app.include_router(web_router)

    @app.get("/healthz", tags=["monitoring"])
    def healthcheck() -> dict[str, str]:  # pragma: no cover - simple endpoint
        return {"status": "ok"}

    return app


__all__ = ["create_app"]
