"""Task queue initialisation."""

from prooforigin.tasks.queue import get_task_queue, register_task, celery_app

# Import job definitions to ensure they are registered with the queue when package is loaded.
from prooforigin.tasks import jobs as _jobs  # noqa: F401

__all__ = ["get_task_queue", "register_task", "celery_app"]

