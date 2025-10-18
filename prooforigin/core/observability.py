"""Observability helpers for monitoring and tracing."""
from __future__ import annotations

from fastapi import FastAPI

from prometheus_fastapi_instrumentator import Instrumentator

from prooforigin.core.logging import get_logger
from prooforigin.core.settings import get_settings

try:  # Optional
    import sentry_sdk
except Exception:  # pragma: no cover
    sentry_sdk = None  # type: ignore

logger = get_logger(__name__)


def configure_observability(app: FastAPI) -> None:
    settings = get_settings()

    if settings.enable_prometheus:
        Instrumentator().instrument(app, metric_namespace=settings.metrics_namespace).expose(
            app, include_in_schema=False
        )

    if settings.sentry_dsn:
        if sentry_sdk is None:  # pragma: no cover - optional dependency not installed
            logger.warning("sentry_not_available", dsn="configured_but_missing_dependency")
            return
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=0.2,
            environment=settings.environment,
        )
        logger.info("sentry_initialised", environment=settings.environment)


__all__ = ["configure_observability"]
