"""Webhook subscription endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from prooforigin.api.dependencies.auth import get_current_user
from prooforigin.api.dependencies.database import get_db
from prooforigin.api import schemas
from prooforigin.core import models

router = APIRouter(prefix="/api/v1", tags=["webhooks"])


@router.get("/webhooks", response_model=list[schemas.WebhookSubscriptionResponse])
def list_webhooks(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[schemas.WebhookSubscriptionResponse]:
    subs = (
        db.query(models.WebhookSubscription)
        .filter(models.WebhookSubscription.user_id == current_user.id)
        .all()
    )
    return [
        schemas.WebhookSubscriptionResponse(
            id=sub.id,
            target_url=sub.target_url,
            event=sub.event,
            created_at=sub.created_at,
            is_active=sub.is_active,
        )
        for sub in subs
    ]


@router.post("/webhooks", response_model=schemas.WebhookSubscriptionResponse, status_code=status.HTTP_201_CREATED)
def create_webhook(
    payload: schemas.WebhookSubscriptionCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.WebhookSubscriptionResponse:
    subscription = models.WebhookSubscription(
        user_id=current_user.id,
        target_url=payload.target_url,
        event=payload.event,
        secret=payload.secret,
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return schemas.WebhookSubscriptionResponse(
        id=subscription.id,
        target_url=subscription.target_url,
        event=subscription.event,
        created_at=subscription.created_at,
        is_active=subscription.is_active,
    )


@router.delete("/webhooks/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook(
    subscription_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    subscription = db.get(models.WebhookSubscription, subscription_id)
    if not subscription or subscription.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    subscription.is_active = False
    db.add(subscription)
    db.commit()


__all__ = ["router"]

