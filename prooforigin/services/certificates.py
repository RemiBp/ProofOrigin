"""Generate signed PDF certificates for proofs."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from prooforigin.core import models
from prooforigin.core.settings import get_settings


def build_certificate(proof: models.Proof, owner: models.User | None) -> bytes:
    settings = get_settings()
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setTitle(f"ProofOrigin Certificate - {proof.id}")
    pdf.setFillColor(colors.HexColor("#1F2937"))
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(30 * mm, height - 40 * mm, "ProofOrigin Certification")

    pdf.setFont("Helvetica", 12)
    pdf.setFillColor(colors.black)
    text_y = height - 60 * mm
    pdf.drawString(30 * mm, text_y, f"Certificate ID: {proof.id}")
    text_y -= 10 * mm
    pdf.drawString(30 * mm, text_y, f"Hash (SHA-256): {proof.file_hash}")
    text_y -= 10 * mm
    pdf.drawString(30 * mm, text_y, f"Signature: {proof.signature[:64]}...")
    text_y -= 10 * mm
    owner_label = owner.display_name or owner.email if owner else "Unknown"
    pdf.drawString(30 * mm, text_y, f"Owner: {owner_label}")
    text_y -= 10 * mm
    created_at = proof.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    pdf.drawString(30 * mm, text_y, f"Created at: {created_at}")
    text_y -= 10 * mm
    anchored = proof.anchored_at.strftime("%Y-%m-%d %H:%M:%S UTC") if proof.anchored_at else "Pending"
    pdf.drawString(30 * mm, text_y, f"Anchored at: {anchored}")
    text_y -= 10 * mm
    tx = proof.blockchain_tx or "Not anchored"
    pdf.drawString(30 * mm, text_y, f"Anchor reference: {tx}")

    pdf.setFont("Helvetica", 11)
    pdf.setFillColor(colors.HexColor("#4B5563"))
    footer_y = 25 * mm
    pdf.drawString(30 * mm, footer_y, settings.app_name)
    pdf.drawRightString(width - 30 * mm, footer_y, datetime.utcnow().strftime("Issued on %d %b %Y"))

    pdf.showPage()
    pdf.save()

    buffer.seek(0)
    return buffer.read()


__all__ = ["build_certificate"]
