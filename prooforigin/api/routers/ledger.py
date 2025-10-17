"""Ledger and admin-facing proof detail routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from prooforigin.api import schemas
from prooforigin.api.dependencies.auth import get_current_user
from prooforigin.api.dependencies.database import get_db
from prooforigin.core import models

router = APIRouter(prefix="/api/v1", tags=["ledger"])


def _can_access(user: models.User, proof: models.Proof) -> bool:
    if user.is_admin:
        return True
    return proof.user_id == user.id


@router.get("/ledger/{proof_id}", response_model=schemas.LedgerEntryResponse)
def get_ledger_entry(
    proof_id: uuid.UUID,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.LedgerEntryResponse:
    proof = db.get(models.Proof, proof_id)
    if not proof:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proof not found")

    if not _can_access(current_user, proof):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    matches = [
        {
            "score": match.score,
            "matched_proof_id": str(match.matched_proof_id) if match.matched_proof_id else None,
            "details": match.details or {},
        }
        for match in proof.matches
    ]
    alerts = [
        {
            "score": alert.score,
            "status": alert.status,
            "match_proof_id": str(alert.match_proof_id) if alert.match_proof_id else None,
        }
        for alert in proof.alerts
    ]

    return schemas.LedgerEntryResponse(
        id=proof.id,
        user_id=proof.user_id,
        file_hash=proof.file_hash,
        signature=proof.signature,
        metadata=proof.metadata,
        created_at=proof.created_at,
        anchored_at=proof.anchored_at,
        blockchain_tx=proof.blockchain_tx,
        anchor_signature=proof.anchor_signature,
        anchor_batch_id=proof.anchor_batch_id,
        matches=matches,
        alerts=alerts,
    )
