"""Notification helpers (email/webhook placeholders)."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Any

from prooforigin.core.logging import get_logger
from prooforigin.core.settings import get_settings

logger = get_logger(__name__)


def send_email(message: dict[str, Any]) -> None:
    """Send an email using SMTP configuration if provided."""

    settings = get_settings()
    smtp_host = message.get("smtp_host") or getattr(settings, "smtp_host", None)
    smtp_port = int(message.get("smtp_port") or getattr(settings, "smtp_port", 0) or 0)
    smtp_username = message.get("smtp_username") or getattr(settings, "smtp_username", None)
    smtp_password = message.get("smtp_password") or getattr(settings, "smtp_password", None)

    recipient = message.get("to")
    if not recipient:
        logger.warning("email_missing_recipient", payload=message)
        return

    email = EmailMessage()
    email["Subject"] = message.get("subject", "ProofOrigin notification")
    email["From"] = message.get("from") or getattr(settings, "smtp_from", "noreply@prooforigin.io")
    email["To"] = recipient
    email.set_content(message.get("body", ""))

    if not smtp_host:
        logger.info("email_logged", recipient=recipient)
        return

    try:
        with smtplib.SMTP(smtp_host, smtp_port or 25, timeout=10) as smtp:
            if smtp_username and smtp_password:
                smtp.starttls()
                smtp.login(smtp_username, smtp_password)
            smtp.send_message(email)
        logger.info("email_sent", recipient=recipient)
    except Exception as exc:  # pragma: no cover - network I/O
        logger.error("email_failed", recipient=recipient, error=str(exc))


__all__ = ["send_email"]

