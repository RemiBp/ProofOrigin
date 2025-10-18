"""Badge rendering endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from prooforigin.api.dependencies.database import get_db
from prooforigin.core import models
from prooforigin.services.badges import build_badge_payload, build_badge_svg

router = APIRouter(prefix="/badge", tags=["badges"])


@router.get("/{file_hash}.svg")
def badge_svg(file_hash: str, db: Session = Depends(get_db)) -> Response:
    proof = db.query(models.Proof).filter(models.Proof.file_hash == file_hash).first()
    if not proof:
        raise HTTPException(status_code=404, detail="Proof not found")
    owner = db.get(models.User, proof.user_id)
    svg = build_badge_svg(proof, owner)
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/{file_hash}.json")
def badge_json(file_hash: str, db: Session = Depends(get_db)) -> JSONResponse:
    proof = db.query(models.Proof).filter(models.Proof.file_hash == file_hash).first()
    if not proof:
        raise HTTPException(status_code=404, detail="Proof not found")
    owner = db.get(models.User, proof.user_id)
    payload = build_badge_payload(proof, owner)
    return JSONResponse(payload)


__all__ = ["router"]
