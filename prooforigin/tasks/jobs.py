"""Registered background jobs."""
from __future__ import annotations

import uuid
from typing import Any

from prooforigin.core.logging import get_logger
from prooforigin.services.blockchain import schedule_anchor
from prooforigin.services.similarity import SimilarityEngine
from prooforigin.services.webhooks import process_delivery_queue
from prooforigin.tasks.queue import register_task

logger = get_logger(__name__)


@register_task("prooforigin.anchor_proof")
def anchor_proof_job(proof_id: str) -> None:
    try:
        schedule_anchor(uuid.UUID(proof_id))
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("anchor_job_failed", proof_id=proof_id, error=str(exc))


@register_task("prooforigin.reindex_similarity")
def reindex_similarity_job(proof_id: str) -> None:
    from prooforigin.core.database import session_scope
    from prooforigin.core import models

    with session_scope() as session:
        proof = session.get(models.Proof, uuid.UUID(proof_id))
        if not proof:
            logger.warning("reindex_missing_proof", proof_id=proof_id)
            return
        engine = SimilarityEngine()
        engine.update_similarity_matches(session, proof)
        session.commit()


@register_task("prooforigin.process_webhooks")
def process_webhooks_job() -> None:
    process_delivery_queue()


@register_task("prooforigin.send_email")
def send_email_job(message: dict[str, Any]) -> None:
    from prooforigin.services import notifications

    notifications.send_email(message)


__all__ = [
    "anchor_proof_job",
    "reindex_similarity_job",
    "process_webhooks_job",
    "send_email_job",
]

