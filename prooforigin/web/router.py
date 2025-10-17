"""Jinja powered dashboard views."""
from __future__ import annotations

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


@router.get("/", response_class=HTMLResponse, tags=["web"])
def landing_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/dashboard", response_class=HTMLResponse, tags=["web"])
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    proofs = db.query(models.Proof).order_by(models.Proof.created_at.desc()).limit(25).all()
    return templates.TemplateResponse("dashboard.html", {"request": request, "proofs": proofs})


__all__ = ["router"]
