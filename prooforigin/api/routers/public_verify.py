"""Public verification endpoints returning shareable proof status."""
from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from prooforigin.api import schemas
from prooforigin.api.dependencies.database import get_db
from prooforigin.core import models
from prooforigin.core.logging import get_logger
from prooforigin.services.certificates import build_certificate
from prooforigin.services.webhooks import queue_event

logger = get_logger(__name__)

router = APIRouter(prefix="/verify", tags=["public-verify"])


@router.get("/{file_hash}", response_model=schemas.PublicProofStatus)
def public_verify(
    file_hash: str,
    request: Request,
    db: Session = Depends(get_db),
) -> schemas.PublicProofStatus:
    proof = db.query(models.Proof).filter(models.Proof.file_hash == file_hash).first()
    requester_ip = request.client.host if request.client else None

    verification = models.Verification(
        proof_id=proof.id if proof else None,
        hash=file_hash,
        success=bool(proof),
        requester_ip=requester_ip,
    )
    db.add(verification)

    if not proof:
        db.commit()
        return schemas.PublicProofStatus(
            hash=file_hash,
            status="missing",
            created_at=None,
            owner=None,
            download_url=None,
            blockchain_tx=None,
            anchored=False,
            proof_id=None,
        )

    owner = proof.user
    db.commit()
    queue_event(
        owner.id,
        "proof.verified.public",
        {
            "proof_id": str(proof.id),
            "hash": proof.file_hash,
            "requester_ip": requester_ip,
        },
    )

    return schemas.PublicProofStatus(
        hash=proof.file_hash,
        status="verified",
        created_at=proof.created_at,
        owner={
            "id": str(owner.id),
            "email": owner.email,
            "display_name": owner.display_name,
        },
        download_url=f"/verify/{proof.file_hash}/certificate",
        blockchain_tx=proof.blockchain_tx,
        anchored=bool(proof.blockchain_tx),
        proof_id=proof.id,
    )


@router.get("/{file_hash}/certificate")
def public_certificate(
    file_hash: str,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    proof = db.query(models.Proof).filter(models.Proof.file_hash == file_hash).first()
    if not proof:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proof not found")

    pdf_bytes = build_certificate(proof, proof.user)
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="proof-{proof.id}.pdf"'},
    )


__all__ = ["router"]
