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

    def list_entries(
        self,
        db: Session,
        *,
        page: int = 1,
        page_size: int = 50,
        profile: str | None = None,
        model: str | None = None,
        asset_hash: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[models.TransparencyLogEntry], int]:
        query = db.query(models.TransparencyLogEntry).outerjoin(models.Proof)
        if profile:
            query = query.filter(models.Proof.metadata_json.isnot(None))
            query = query.filter(models.Proof.metadata_json["profile"].astext == profile)
        if model:
            query = query.filter(models.Proof.metadata_json.isnot(None))
            query = query.filter(models.Proof.metadata_json["model"].astext == model)
        if asset_hash:
            query = query.filter(models.TransparencyLogEntry.file_hash == asset_hash)
        if date_from:
            query = query.filter(models.TransparencyLogEntry.created_at >= date_from)
        if date_to:
            query = query.filter(models.TransparencyLogEntry.created_at <= date_to)
        total = query.count()
        entries = (
            query.order_by(models.TransparencyLogEntry.sequence.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return entries, total

    def serialize_entry(self, entry: models.TransparencyLogEntry) -> dict[str, object]:
        receipts = [
            {
                "chain": receipt.chain,
                "transaction_hash": receipt.transaction_hash,
                "anchored_at": receipt.anchored_at.isoformat() if receipt.anchored_at else None,
                "payload": receipt.receipt_payload,
            }
            for receipt in entry.receipts
        ]
        return {
            "id": str(entry.id),
            "proof_id": str(entry.proof_id) if entry.proof_id else None,
            "profile": entry.proof.metadata_json.get("profile") if entry.proof else None,
            "asset_hash": entry.file_hash,
            "anchored_at": entry.anchored_at.isoformat() if entry.anchored_at else None,
            "created_at": entry.created_at.isoformat(),
            "receipts": receipts,
            "chain": receipts[0]["chain"] if receipts else None,
            "model": entry.proof.metadata_json.get("model") if entry.proof else None,
            "metadata": entry.proof.metadata_json if entry.proof else None,
            "sequence": entry.sequence,
        }


__all__ = ["TransparencyLedger", "LedgerReceipt"]
