"""Webhook subscription and delivery services."""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta
from typing import Any

import requests
from sqlalchemy import and_

from prooforigin.core import models
from prooforigin.core.database import session_scope
from prooforigin.core.logging import get_logger
from prooforigin.core.settings import get_settings
from prooforigin.tasks.queue import get_task_queue

logger = get_logger(__name__)


def _sign_payload(secret: str | None, payload: dict[str, Any]) -> str | None:
    if not secret:
        return None
    message = json.dumps(payload, sort_keys=True).encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def queue_event(user_id: uuid.UUID | None, event: str, payload: dict[str, Any]) -> None:
    """Persist deliveries and enqueue processing."""

    with session_scope() as session:
        query = session.query(models.WebhookSubscription).filter(models.WebhookSubscription.is_active.is_(True))
        if user_id:
            query = query.filter(models.WebhookSubscription.user_id == user_id)
        subs = query.filter(models.WebhookSubscription.event == event).all()
        if not subs:
            return
        for sub in subs:
            delivery = models.WebhookDelivery(
                subscription_id=sub.id,
                payload=payload,
                attempts=0,
                next_retry_at=datetime.utcnow(),
            )
            session.add(delivery)
        session.commit()

    get_task_queue().enqueue("prooforigin.process_webhooks")


def _deliver(subscription: models.WebhookSubscription, delivery: models.WebhookDelivery) -> tuple[int | None, bool]:
    settings = get_settings()
    headers = {"User-Agent": "ProofOrigin/1.0"}
    signature = _sign_payload(subscription.secret or settings.webhook_hmac_secret, delivery.payload)
    if signature:
        headers["X-ProofOrigin-Signature"] = signature
    try:
        response = requests.post(
            subscription.target_url,
            json=delivery.payload,
            timeout=10,
            headers=headers,
        )
        return response.status_code, response.ok
    except Exception as exc:  # pragma: no cover - network IO
        logger.warning("webhook_delivery_failed", id=delivery.id, error=str(exc))
        return None, False


def process_delivery_queue(limit: int = 25) -> None:
    settings = get_settings()
    now = datetime.utcnow()
    with session_scope() as session:
        deliveries = (
            session.query(models.WebhookDelivery)
            .join(models.WebhookSubscription)
            .filter(models.WebhookSubscription.is_active.is_(True))
            .filter(models.WebhookDelivery.delivered_at.is_(None))
            .filter(
                and_(
                    models.WebhookDelivery.next_retry_at.isnot(None),
                    models.WebhookDelivery.next_retry_at <= now,
                )
            )
            .limit(limit)
            .all()
        )

        for delivery in deliveries:
            subscription = delivery.subscription
            status_code, success = _deliver(subscription, delivery)
            delivery.status_code = status_code
            delivery.attempts += 1
            if success:
                delivery.delivered_at = datetime.utcnow()
                delivery.next_retry_at = None
                logger.info(
                    "webhook_delivered",
                    delivery_id=delivery.id,
                    subscription_id=subscription.id,
                    status=status_code,
                )
            else:
                if delivery.attempts >= settings.webhook_retry_max:
                    delivery.next_retry_at = None
                    logger.warning(
                        "webhook_exhausted",
                        delivery_id=delivery.id,
                        attempts=delivery.attempts,
                    )
                else:
                    backoff_seconds = settings.webhook_retry_backoff_seconds * (2 ** (delivery.attempts - 1))
                    delivery.next_retry_at = datetime.utcnow() + timedelta(seconds=backoff_seconds)
            session.add(delivery)
        session.commit()


__all__ = ["queue_event", "process_delivery_queue"]

