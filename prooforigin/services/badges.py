"""Generate dynamic badges for public embedding."""
from __future__ import annotations

from datetime import datetime

from prooforigin.core import models
from prooforigin.core.settings import get_settings


def build_badge_payload(proof: models.Proof, owner: models.User | None) -> dict[str, str]:
    issued = proof.created_at.strftime("%Y-%m-%d")
    owner_label = owner.display_name or owner.email if owner else "Unknown"
    return {
        "hash": proof.file_hash[:16],
        "proof_id": str(proof.id),
        "issued_on": issued,
        "owner": owner_label,
        "status": "Anchored" if proof.blockchain_tx else "Pending",
    }


def build_badge_svg(proof: models.Proof, owner: models.User | None) -> str:
    payload = build_badge_payload(proof, owner)
    settings = get_settings()
    status_color = "#16a34a" if proof.blockchain_tx else "#facc15"
    return f"""
<svg xmlns="http://www.w3.org/2000/svg" width="340" height="120" viewBox="0 0 340 120">
  <rect width="340" height="120" rx="12" fill="#111827"/>
  <text x="20" y="40" fill="#f9fafb" font-family="Helvetica" font-weight="bold" font-size="18">{settings.app_name} Certified</text>
  <text x="20" y="65" fill="#d1d5db" font-family="Helvetica" font-size="12">Owner: {payload['owner']}</text>
  <text x="20" y="80" fill="#9ca3af" font-family="Helvetica" font-size="12">Hash: {payload['hash']}</text>
  <text x="20" y="95" fill="{status_color}" font-family="Helvetica" font-size="12">Status: {payload['status']}</text>
</svg>
"""


__all__ = ["build_badge_payload", "build_badge_svg"]
