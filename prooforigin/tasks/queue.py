"""Task queue abstraction for ProofOrigin."""
from __future__ import annotations

from typing import Any, Callable

try:  # Optional dependency
    from celery import Celery
except ImportError:  # pragma: no cover
    Celery = None  # type: ignore

from prooforigin.core.logging import get_logger
from prooforigin.core.settings import get_settings

logger = get_logger(__name__)

celery_app: Celery | None = None
INLINE_TASKS: dict[str, Callable[..., Any]] = {}


def _init_celery() -> None:
    global celery_app
    settings = get_settings()
    if Celery is None:
        return
    if settings.task_queue_backend != "celery":
        return
    if not settings.celery_broker_url:
        logger.warning("celery_disabled", reason="broker_missing")
        return
    if celery_app is None:
        celery_app = Celery(
            "prooforigin",
            broker=settings.celery_broker_url,
            backend=settings.celery_result_backend or settings.celery_broker_url,
        )
        celery_app.conf.update(
            task_serializer="json",
            result_serializer="json",
            accept_content=["json"],
            timezone="UTC",
            task_acks_late=True,
            worker_max_tasks_per_child=1000,
        )
        logger.info("celery_initialised", broker=settings.celery_broker_url)


_init_celery()


def register_task(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to register a task for inline execution and Celery dispatch."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        INLINE_TASKS[name] = func
        if celery_app is not None:
            celery_app.task(name=name)(func)
        return func

    return decorator


class TaskQueue:
    """Simple task queue that falls back to synchronous execution."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def enqueue(self, task_name: str, *args: Any, **kwargs: Any) -> Any:
        if celery_app is not None:
            return celery_app.send_task(task_name, args=args, kwargs=kwargs)
        task = INLINE_TASKS.get(task_name)
        if not task:
            raise ValueError(f"Task '{task_name}' is not registered")
        return task(*args, **kwargs)


_task_queue: TaskQueue | None = None


def get_task_queue() -> TaskQueue:
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue()
    return _task_queue


__all__ = ["celery_app", "get_task_queue", "register_task", "INLINE_TASKS"]

