"""Rate limiting utilities using SlowAPI."""
from __future__ import annotations

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from prooforigin.core.settings import get_settings

_limiter: Limiter | None = None


def get_limiter() -> Limiter:
    global _limiter
    if _limiter is None:
        settings = get_settings()
        _limiter = Limiter(
            key_func=get_remote_address,
            default_limits=[
                f"{settings.rate_limit_requests}/{settings.rate_limit_window_seconds} seconds"
            ],
            storage_uri=settings.resolved_rate_limit_storage,
        )
    return _limiter


def setup_rate_limiting(app: FastAPI) -> None:
    limiter = get_limiter()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests",
            "limit": exc.detail,
        },
        headers={"Retry-After": str(exc.reset_in)},
    )


__all__ = ["get_limiter", "setup_rate_limiting"]
