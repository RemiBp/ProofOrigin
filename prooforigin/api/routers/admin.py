"""Administrative API endpoints for monitoring users and proofs."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from prooforigin.api import schemas
from prooforigin.api.dependencies.auth import get_admin_user
from prooforigin.api.dependencies.database import get_db
from prooforigin.core import models

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/users", response_model=list[schemas.AdminUserSummary])
def list_users(
    _: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> list[schemas.AdminUserSummary]:
    users = db.query(models.User).order_by(models.User.created_at.desc()).all()
    return [
        schemas.AdminUserSummary(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            credits=user.credits,
            is_verified=user.is_verified,
            kyc_level=user.kyc_level,
            created_at=user.created_at,
        )
        for user in users
    ]


@router.get("/proofs", response_model=list[schemas.AdminProofSummary])
def list_proofs(
    _: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> list[schemas.AdminProofSummary]:
    proofs = db.query(models.Proof).order_by(models.Proof.created_at.desc()).all()
    summaries: list[schemas.AdminProofSummary] = []
    for proof in proofs:
        suspicious = sum(1 for match in proof.matches if match.score >= 0.8)
        summaries.append(
            schemas.AdminProofSummary(
                id=proof.id,
                user_id=proof.user_id,
                file_name=proof.file_name,
                created_at=proof.created_at,
                anchored_at=proof.anchored_at,
                blockchain_tx=proof.blockchain_tx,
                suspicious_matches=suspicious,
            )
        )
    return summaries
