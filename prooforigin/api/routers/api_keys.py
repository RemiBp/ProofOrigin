"""API key management endpoints."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from prooforigin.api import schemas
from prooforigin.api.dependencies.auth import get_current_user
from prooforigin.api.dependencies.database import get_db
from prooforigin.core import models

router = APIRouter(prefix="/api/v1/api-keys", tags=["api-keys"])


@router.get("/", response_model=list[schemas.ApiKeyResponse])
def list_api_keys(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[schemas.ApiKeyResponse]:
    keys = (
        db.query(models.ApiKey)
        .filter(models.ApiKey.user_id == current_user.id)
        .order_by(models.ApiKey.created_at.desc())
        .all()
    )
    return [
        schemas.ApiKeyResponse(
            id=key.id,
            key=key.key,
            quota=key.quota,
            created_at=key.created_at,
            last_used_at=key.last_used_at,
        )
        for key in keys
    ]


@router.post("/", response_model=schemas.ApiKeyResponse, status_code=status.HTTP_201_CREATED)
def create_api_key(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.ApiKeyResponse:
    active_keys = (
        db.query(models.ApiKey)
        .filter(models.ApiKey.user_id == current_user.id)
        .count()
    )
    if active_keys >= 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="API key limit reached")

    key_value = secrets.token_hex(32)
    api_key = models.ApiKey(user_id=current_user.id, key=key_value, quota=current_user.credits)
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return schemas.ApiKeyResponse(
        id=api_key.id,
        key=api_key.key,
        quota=api_key.quota,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
    )


@router.delete("/{api_key_id}", status_code=status.HTTP_202_ACCEPTED)
def revoke_api_key(
    api_key_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    api_key = db.get(models.ApiKey, api_key_id)
    if not api_key or api_key.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    db.delete(api_key)
    db.commit()


__all__ = ["router"]
