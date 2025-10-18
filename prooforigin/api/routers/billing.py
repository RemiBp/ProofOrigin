"""Billing and quota endpoints."""
from __future__ import annotations

import json
import uuid

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from prooforigin.api import schemas
from prooforigin.api.dependencies.auth import get_current_user
from prooforigin.api.dependencies.database import get_db
from prooforigin.core import models
from prooforigin.core.plans import PlanDetails, get_plan_details
from prooforigin.core.settings import get_settings

router = APIRouter(prefix="/api/v1", tags=["billing"])
settings = get_settings()


def _resolve_price_id(plan: str) -> str | None:
    if plan == "pro":
        return settings.stripe_price_pro or settings.stripe_price_id
    if plan == "business":
        return settings.stripe_price_business
    return None


def _apply_plan(user: models.User, plan_details: PlanDetails, db: Session) -> None:
    user.subscription_plan = plan_details.name
    if user.credits < plan_details.default_credits:
        user.credits = plan_details.default_credits
    for key in user.api_keys:
        key.quota = plan_details.monthly_quota
        db.add(key)
    db.add(user)


@router.post("/buy-credits", response_model=schemas.StripeCheckoutResponse)
def buy_credits(
    payload: schemas.StripeCheckoutRequest | None = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.StripeCheckoutResponse:
    plan_name = (payload.plan if payload else "pro").lower()
    plan_details = get_plan_details(plan_name)

    if plan_details.name == "free":
        _apply_plan(current_user, plan_details, db)
        db.commit()
        return schemas.StripeCheckoutResponse(
            checkout_url="https://app.prooforigin.com/pricing?plan=free",
            credits=current_user.credits,
            plan=current_user.subscription_plan,
        )

    price_id = _resolve_price_id(plan_details.name)
    if not settings.stripe_api_key or not price_id:
        fake_url = f"https://billing.prooforigin.dev/checkout?user={current_user.id}&plan={plan_details.name}"
        _apply_plan(current_user, plan_details, db)
        db.add(
            models.Payment(
                user_id=current_user.id,
                stripe_charge=f"simulated-{uuid.uuid4().hex}",
                credits=plan_details.default_credits,
            )
        )
        db.commit()
        return schemas.StripeCheckoutResponse(
            checkout_url=fake_url,
            credits=current_user.credits,
            plan=current_user.subscription_plan,
        )

    try:
        stripe.api_key = settings.stripe_api_key
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=current_user.email,
            success_url="https://app.prooforigin.com/dashboard?status=success",
            cancel_url="https://app.prooforigin.com/dashboard?status=cancel",
            metadata={"user_id": str(current_user.id), "plan": plan_details.name},
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

    return schemas.StripeCheckoutResponse(
        checkout_url=session.url,
        credits=current_user.credits,
        plan=plan_details.name,
    )


@router.post("/stripe/webhook", status_code=status.HTTP_202_ACCEPTED)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> None:
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    stripe.api_key = settings.stripe_api_key
    if settings.stripe_webhook_secret and sig_header:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.stripe_webhook_secret
            )
        except Exception as exc:  # pragma: no cover - signature validation
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature") from exc
    else:
        data = json.loads(payload.decode() or "{}")
        event = stripe.Event.construct_from(data, stripe.api_key or "")

    event_type = event.get("type")
    data_object = event.get("data", {}).get("object", {})
    metadata = data_object.get("metadata", {})
    user_id = metadata.get("user_id")
    if not user_id:
        return

    user = db.get(models.User, user_id)
    if not user:
        return

    if event_type == "checkout.session.completed":
        plan = metadata.get("plan", "pro")
        plan_details = get_plan_details(plan)
        _apply_plan(user, plan_details, db)
        db.add(
            models.Payment(
                user_id=user.id,
                stripe_charge=data_object.get("id", "unknown"),
                credits=plan_details.default_credits,
                checkout_session=data_object.get("id"),
            )
        )
        db.commit()
    elif event_type == "invoice.payment_failed":
        _apply_plan(user, get_plan_details("free"), db)
        user.is_active = False
        db.add(user)
        db.commit()


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

    plan_details = get_plan_details(current_user.subscription_plan)

    return schemas.UsageResponse(
        proofs_generated=proofs_generated,
        verifications_performed=verifications,
        remaining_credits=current_user.credits,
        last_payment=last_payment.created_at if last_payment else None,
        next_anchor_batch=next_batch.created_at if next_batch else None,
        plan=plan_details.name,
        rate_limit_per_minute=plan_details.per_minute,
        monthly_quota=plan_details.monthly_quota,
    )
