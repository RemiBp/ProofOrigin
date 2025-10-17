"""Billing and quota endpoints."""
from __future__ import annotations

import uuid

import stripe
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from prooforigin.api import schemas
from prooforigin.api.dependencies.auth import get_current_user
from prooforigin.api.dependencies.database import get_db
from prooforigin.core import models
from prooforigin.core.settings import get_settings

router = APIRouter(prefix="/api/v1", tags=["billing"])
settings = get_settings()


@router.post("/buy-credits", response_model=schemas.StripeCheckoutResponse)
def buy_credits(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.StripeCheckoutResponse:
    if not settings.stripe_api_key or not settings.stripe_price_id:
        # Simulate checkout URL for development
        fake_url = f"https://billing.prooforigin.dev/checkout?user={current_user.id}"
        current_user.credits += settings.default_credit_pack
        db.add(current_user)
        db.add(
            models.Payment(
                user_id=current_user.id,
                stripe_charge=f"simulated-{uuid.uuid4().hex}",
                credits=settings.default_credit_pack,
            )
        )
        db.commit()
        return schemas.StripeCheckoutResponse(checkout_url=fake_url, credits=current_user.credits)

    try:
        stripe.api_key = settings.stripe_api_key
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
            customer_email=current_user.email,
            success_url="https://app.prooforigin.com/dashboard?status=success",
            cancel_url="https://app.prooforigin.com/dashboard?status=cancel",
            metadata={"user_id": str(current_user.id)},
        )
    except Exception as exc:  # pragma: no cover - depends on Stripe API
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Stripe error") from exc

    db.add(
        models.Payment(
            user_id=current_user.id,
            stripe_charge=session.id,
            checkout_session=session.id,
            credits=0,
        )
    )
    db.commit()

    return schemas.StripeCheckoutResponse(checkout_url=session.url, credits=current_user.credits)


@router.get("/usage", response_model=schemas.UsageResponse)
def usage(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.UsageResponse:
    proofs_generated = db.query(models.Proof).filter(models.Proof.user_id == current_user.id).count()
    verifications = (
        db.query(models.UsageLog)
        .filter(models.UsageLog.user_id == current_user.id)
        .filter(models.UsageLog.action.in_(["verify_proof", "verify_proof_file"]))
        .count()
    )
    last_payment = (
        db.query(models.Payment)
        .filter(models.Payment.user_id == current_user.id)
        .order_by(models.Payment.created_at.desc())
        .first()
    )
    next_batch = (
        db.query(models.AnchorBatch)
        .join(models.Proof, models.Proof.anchor_batch_id == models.AnchorBatch.id)
        .filter(models.Proof.user_id == current_user.id)
        .filter(models.AnchorBatch.status == "pending")
        .order_by(models.AnchorBatch.created_at.asc())
        .first()
    )

    return schemas.UsageResponse(
        proofs_generated=proofs_generated,
        verifications_performed=verifications,
        remaining_credits=current_user.credits,
        last_payment=last_payment.created_at if last_payment else None,
        next_anchor_batch=next_batch.created_at if next_batch else None,
    )
