"""Rate limiting utilities using SlowAPI."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

try:  # pragma: no cover - optional dependency
    from slowapi import Limiter
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from slowapi.util import get_remote_address
except ImportError:  # pragma: no cover
    Limiter = None  # type: ignore
    RateLimitExceeded = None  # type: ignore
    SlowAPIMiddleware = None  # type: ignore
    get_remote_address = None  # type: ignore

from typing import Any, Callable

from prooforigin.core.logging import get_logger
from prooforigin.core.settings import get_settings

logger = get_logger(__name__)

class _DummyLimiter:
    def limit(self, *args: Any, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            return func

        return decorator


_limiter: "Limiter | None" = None


def get_limiter() -> Limiter:
    global _limiter
    if _limiter is None and Limiter is not None and get_remote_address is not None:
        settings = get_settings()
        _limiter = Limiter(
            key_func=get_remote_address,
            default_limits=[
                f"{settings.rate_limit_requests}/{settings.rate_limit_window_seconds} seconds"
            ],
            storage_uri=settings.resolved_rate_limit_storage,
        )
    if _limiter is None:
        _limiter = _DummyLimiter()
    return _limiter


def setup_rate_limiting(app: FastAPI) -> None:
    limiter = get_limiter()
    app.state.limiter = limiter
    if isinstance(limiter, _DummyLimiter) or SlowAPIMiddleware is None or RateLimitExceeded is None:
        logger.warning("rate_limiting_disabled", reason="slowapi_missing")
        return
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)


def _rate_limit_handler(request: Request, exc: Any) -> JSONResponse:
    if RateLimitExceeded is None or not isinstance(exc, RateLimitExceeded):  # pragma: no cover - defensive
        return JSONResponse(status_code=429, content={"detail": "Too many requests"})
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests",
            "limit": exc.detail,
        },
        headers={"Retry-After": str(exc.reset_in)},
    )


__all__ = ["get_limiter", "setup_rate_limiting"]
