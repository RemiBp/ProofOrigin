"""API key authentication helpers."""
from __future__ import annotations

from datetime import datetime, timedelta
from datetime import datetime

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from prooforigin.core import models
from prooforigin.core.plans import get_plan_details

from .database import get_db


def get_api_key_record(
    x_api_key: str = Header(alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> models.ApiKey:
    api_key = db.query(models.ApiKey).filter(models.ApiKey.key == x_api_key).first()
    if not api_key or not api_key.user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    _enforce_plan_limits(api_key.user, db)

    api_key.last_used_at = datetime.utcnow()
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return api_key


def get_api_key_user(api_key: models.ApiKey = Depends(get_api_key_record)) -> models.User:
    return api_key.user


def _enforce_plan_limits(user: models.User, db: Session) -> None:
    limits = get_plan_details(user.subscription_plan)
    window_start = datetime.utcnow() - timedelta(minutes=1)
    minute_usage = (
        db.query(models.UsageLog)
        .filter(models.UsageLog.user_id == user.id)
        .filter(models.UsageLog.created_at >= window_start)
        .filter(models.UsageLog.action.in_(["public_api.proof", "public_api.verify", "public_api.batch"]))
        .count()
    )
    if minute_usage >= limits.per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded for {limits.name} plan",
        )

    month_start = datetime.utcnow() - timedelta(days=30)
    monthly_usage = (
        db.query(models.UsageLog)
        .filter(models.UsageLog.user_id == user.id)
        .filter(models.UsageLog.created_at >= month_start)
        .filter(models.UsageLog.action.in_(["public_api.proof", "public_api.verify", "public_api.batch"]))
        .count()
    )
    if monthly_usage >= limits.monthly_quota:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Monthly quota exceeded",
        )


__all__ = ["get_api_key_user", "get_api_key_record"]
