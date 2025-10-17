"""FastAPI application factory."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from prooforigin.api.routers import auth, billing, proofs
from prooforigin.core.database import init_database
from prooforigin.core.logging import setup_logging
from prooforigin.core.settings import get_settings
from prooforigin.web.router import router as web_router


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

    app.include_router(auth.router)
    app.include_router(proofs.router)
    app.include_router(billing.router)
    app.include_router(web_router)

    @app.get("/healthz", tags=["monitoring"])
    def healthcheck() -> dict[str, str]:  # pragma: no cover - simple endpoint
        return {"status": "ok"}

    return app


__all__ = ["create_app"]
