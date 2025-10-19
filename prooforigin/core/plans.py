"""Subscription plan catalog and helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PlanName = Literal["free", "pro", "business"]


@dataclass(frozen=True, slots=True)
class PlanDetails:
    name: PlanName
    monthly_quota: int
    per_minute: int
    default_credits: int


_PLAN_REGISTRY: dict[PlanName, PlanDetails] = {
    "free": PlanDetails(name="free", monthly_quota=1000, per_minute=30, default_credits=100),
    "pro": PlanDetails(name="pro", monthly_quota=10000, per_minute=240, default_credits=1000),
    "business": PlanDetails(name="business", monthly_quota=100000, per_minute=1200, default_credits=10000),
}


def get_plan_details(plan: str | None) -> PlanDetails:
    """Return plan details defaulting to the free tier."""
    key = (plan or "free").lower()
    return _PLAN_REGISTRY.get(key, _PLAN_REGISTRY["free"])


__all__ = ["PlanDetails", "PlanName", "get_plan_details"]
