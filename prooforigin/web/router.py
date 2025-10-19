"""Jinja powered dashboard views."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from prooforigin.api.dependencies.database import get_db
from prooforigin.core import models

router = APIRouter()
_templates_path = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_templates_path))


def _base_context(request: Request) -> dict[str, object]:
    now = datetime.utcnow()
    return {
        "request": request,
        "current_year": now.year,
        "current_iso": now.replace(microsecond=0).isoformat() + "Z",
        "current_pretty": now.strftime("%d %b %Y %H:%M"),
    }


@router.get("/", response_class=HTMLResponse, tags=["web"])
def landing_page(request: Request) -> HTMLResponse:
    context = _base_context(request)
    return templates.TemplateResponse("index.html", context)


@router.get("/dashboard", response_class=HTMLResponse, tags=["web"])
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    proofs = db.query(models.Proof).order_by(models.Proof.created_at.desc()).limit(25).all()
    context = _base_context(request)
    context.update(
        {
            "proofs": proofs,
            "proofs_payload": [
                {
                    "id": str(proof.id),
                    "file_name": proof.file_name,
                    "mime_type": proof.mime_type,
                    "file_size": proof.file_size,
                    "created_at": proof.created_at.isoformat() if proof.created_at else None,
                    "file_hash": proof.file_hash,
                    "blockchain_tx": proof.blockchain_tx,
                    "matches": [
                        {
                            "score": match.score,
                            "matched_proof_id": str(match.matched_proof_id)
                            if match.matched_proof_id
                            else None,
                        }
                        for match in proof.matches
                    ],
                }
                for proof in proofs
            ],
        }
    )
    return templates.TemplateResponse("dashboard.html", context)


@router.get("/verify/{file_hash}/view", response_class=HTMLResponse, tags=["web"])
def verify_page(file_hash: str, request: Request) -> HTMLResponse:
    context = _base_context(request)
    context["file_hash"] = file_hash
    return templates.TemplateResponse("verify.html", context)


__all__ = ["router"]
