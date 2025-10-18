"""Timestamp backends for ProofOrigin."""
from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy.orm import Session

from prooforigin.core import models
from prooforigin.core.logging import get_logger
from prooforigin.core.settings import Settings, get_settings

logger = get_logger(__name__)


class TimestampAuthority:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def prepare_anchor(self, db: Session, proof: models.Proof, task_queue) -> None:
        backend = getattr(self.settings, "timestamp_backend", "blockchain")
        if proof.blockchain_tx:
            logger.info(
                "timestamp_already_anchored",
                proof_id=str(proof.id),
                tx=proof.blockchain_tx,
            )
            return
        if backend == "opentimestamps":
            commitment = hashlib.sha256(
                f"{proof.file_hash}:{proof.created_at.isoformat()}".encode()
            ).hexdigest()
            proof.blockchain_tx = f"ots://{commitment}"
            proof.anchor_signature = commitment
            proof.anchored_at = datetime.utcnow()
            db.add(proof)
            logger.info(
                "timestamp_ots_recorded",
                proof_id=str(proof.id),
                tx=proof.blockchain_tx,
            )
            return
        if self.settings.blockchain_enabled:
            task_queue.enqueue("prooforigin.anchor_proof", str(proof.id))
        else:
            logger.info("timestamp_blockchain_disabled", proof_id=str(proof.id))


__all__ = ["TimestampAuthority"]
