"""Transparency log and receipt generation utilities."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from prooforigin.core import models
from prooforigin.core.logging import get_logger
from prooforigin.core.secrets import derive_ledgers_signing_key
from prooforigin.core.settings import Settings, get_settings

logger = get_logger(__name__)


@dataclass(slots=True)
class LedgerReceipt:
    chain: str
    transaction_hash: str | None
    anchored_at: datetime | None
    payload: dict[str, object]


class TransparencyLedger:
    """Append-only transparency log inspired by certificate transparency."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._signing_key = derive_ledgers_signing_key(self.settings)

    # ------------------------------------------------------------------
    def _next_sequence(self, db: Session) -> int:
        current = db.query(func.max(models.TransparencyLogEntry.sequence)).scalar()
        return (current or 0) + 1

    def _latest_entry(self, db: Session) -> models.TransparencyLogEntry | None:
        return (
            db.query(models.TransparencyLogEntry)
            .order_by(models.TransparencyLogEntry.sequence.desc())
            .first()
        )

    def _sign_entry(self, payload: dict[str, object]) -> tuple[str, str]:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        digest = hashlib.sha256(encoded).digest()
        signature = self._signing_key.sign(digest)
        return hashlib.sha256(encoded).hexdigest(), base64.b64encode(signature).decode()

    # ------------------------------------------------------------------
    def append(
        self,
        db: Session,
        proof: models.Proof,
        normalized_hash: str,
        merkle_root: str,
        merkle_leaf: str,
        receipts: Sequence[LedgerReceipt],
    ) -> models.TransparencyLogEntry:
        sequence = self._next_sequence(db)
        parent = self._latest_entry(db)
        parent_hash = parent.entry_hash if parent else None

        entry_payload = {
            "sequence": sequence,
            "proof_id": str(proof.id),
            "file_hash": proof.file_hash,
            "normalized_hash": normalized_hash,
            "merkle_root": merkle_root,
            "merkle_leaf": merkle_leaf,
            "parent_hash": parent_hash,
            "timestamp": datetime.utcnow().isoformat(),
            "namespace": self.settings.transparency_log_namespace,
        }
        entry_hash, signature = self._sign_entry(entry_payload)

        entry = models.TransparencyLogEntry(
            sequence=sequence,
            proof_id=proof.id,
            file_hash=proof.file_hash,
            normalized_hash=normalized_hash,
            merkle_root=merkle_root,
            merkle_leaf=merkle_leaf,
            parent_hash=parent_hash,
            entry_hash=entry_hash,
            signature=signature,
            transparency_log=self.settings.transparency_log_namespace,
        )
        db.add(entry)
        db.flush()

        for receipt in receipts:
            db.add(
                models.ChainReceipt(
                    proof_id=proof.id,
                    transparency_entry_id=entry.id,
                    chain=receipt.chain,
                    transaction_hash=receipt.transaction_hash,
                    receipt_payload=receipt.payload,
                    anchored_at=receipt.anchored_at,
                )
            )

        proof.ledger_entry_id = entry.id
        proof.merkle_leaf = merkle_leaf
        db.flush()
        return entry

    # ------------------------------------------------------------------
    def build_receipt_json(
        self, proof: models.Proof, entry: models.TransparencyLogEntry
    ) -> dict[str, object]:
        chain_receipts = (
            entry.receipts
            if entry.receipts
            else proof.chain_receipts
        )
        return {
            "proof_id": str(proof.id),
            "hash": proof.file_hash,
            "normalized_hash": proof.normalized_hash,
            "ledger": {
                "sequence": entry.sequence,
                "entry_hash": entry.entry_hash,
                "signature": entry.signature,
                "namespace": entry.transparency_log,
            },
            "blockchain_receipts": [
                {
                    "chain": receipt.chain,
                    "transaction_hash": receipt.transaction_hash,
                    "payload": receipt.receipt_payload,
                    "anchored_at": receipt.anchored_at.isoformat()
                    if receipt.anchored_at
                    else None,
                }
                for receipt in chain_receipts
            ],
        }


__all__ = ["TransparencyLedger", "LedgerReceipt"]
