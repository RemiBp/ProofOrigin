"""API key authentication helpers."""
from __future__ import annotations

from datetime import datetime

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from prooforigin.core import models

from .database import get_db


def get_api_key_record(
    x_api_key: str = Header(alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> models.ApiKey:
    api_key = db.query(models.ApiKey).filter(models.ApiKey.key == x_api_key).first()
    if not api_key or not api_key.user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    api_key.last_used_at = datetime.utcnow()
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return api_key


def get_api_key_user(api_key: models.ApiKey = Depends(get_api_key_record)) -> models.User:
    return api_key.user


__all__ = ["get_api_key_user", "get_api_key_record"]
