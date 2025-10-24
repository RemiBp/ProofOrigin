"""Logging utilities using structlog."""
from __future__ import annotations

import logging
from typing import Any

try:  # pragma: no cover - optional dependency
    import structlog
except ImportError:  # pragma: no cover
    structlog = None  # type: ignore


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(message)s")
    if structlog is None:
        return
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


class _KeyValueLogger:
    """Minimal adapter to mimic structlog's keyword argument logging."""

    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)

    def _format(self, message: str, kwargs: dict[str, Any]) -> str:
        if not kwargs:
            return message
        pairs = " ".join(f"{key}={value!r}" for key, value in kwargs.items())
        return f"{message} {pairs}" if message else pairs

    def info(self, message: str, **kwargs: Any) -> None:
        self._logger.info(self._format(message, kwargs))

    def warning(self, message: str, **kwargs: Any) -> None:
        self._logger.warning(self._format(message, kwargs))

    def error(self, message: str, **kwargs: Any) -> None:
        self._logger.error(self._format(message, kwargs))

    def debug(self, message: str, **kwargs: Any) -> None:
        self._logger.debug(self._format(message, kwargs))


def get_logger(name: str):
    if structlog is None:
        return _KeyValueLogger(name)
    return structlog.get_logger(name)


__all__ = ["setup_logging", "get_logger"]
