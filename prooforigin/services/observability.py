"""Utilities for instrumenting proof workflows."""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

from prooforigin.core.logging import get_logger

logger = get_logger(__name__)


@contextmanager
def trace_stage(workflow: str, stage: str, **context: object) -> Iterator[None]:
    """Yield while timing a workflow stage and emitting structured logs."""

    start = time.perf_counter()
    log = logger.bind(workflow=workflow, stage=stage, **context)
    log.info("stage_started")
    try:
        yield
    except Exception as exc:
        elapsed = time.perf_counter() - start
        log.error("stage_failed", elapsed_ms=int(elapsed * 1000), error=str(exc))
        raise
    else:
        elapsed = time.perf_counter() - start
        log.info("stage_completed", elapsed_ms=int(elapsed * 1000))


__all__ = ["trace_stage"]
