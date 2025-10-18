"""AI integrations for ProofOrigin."""
from __future__ import annotations

import base64
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from prooforigin.api import schemas
from prooforigin.api.dependencies.api_key import get_api_key_record, get_api_key_user
from prooforigin.api.dependencies.database import get_db
from prooforigin.core import models
from prooforigin.services.proofs import ProofContent, ProofRegistrationService
from prooforigin.services.webhooks import queue_event

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])
registration_service = ProofRegistrationService()


def _build_metadata(payload: schemas.AIProofRequest) -> str | None:
    metadata = payload.metadata.copy() if payload.metadata else {}
    metadata.setdefault(
        "ai",
        {
            "model_name": payload.model_name,
            "prompt": payload.prompt,
        },
    )
    return json.dumps(metadata)


def _decode_ai_payload(payload: schemas.AIProofRequest) -> tuple[ProofContent, str | None]:
    if payload.content:
        try:
            data = base64.b64decode(payload.content)
        except Exception as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid base64 payload") from exc
        filename = f"ai-{uuid.uuid4().hex}.bin"
        return ProofContent(data=data, filename=filename, mime_type="application/octet-stream", is_binary=True), None
    if payload.text:
        data = payload.text.encode("utf-8")
        filename = f"ai-{uuid.uuid4().hex}.txt"
        return ProofContent(data=data, filename=filename, mime_type="text/plain", is_binary=False), payload.text
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing AI content")


@router.post("/proof", response_model=schemas.ProofResponse)
def register_ai_proof(
    payload: schemas.AIProofRequest,
    api_key: models.ApiKey = Depends(get_api_key_record),
    current_user: models.User = Depends(get_api_key_user),
    db: Session = Depends(get_db),
) -> schemas.ProofResponse:
    if api_key.quota <= 0:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="API quota exceeded")

    content, text_payload = _decode_ai_payload(payload)
    metadata_str = _build_metadata(payload)
    try:
        result = registration_service.register_content(
            db,
            current_user,
            content,
            metadata_str,
            payload.key_password,
            text_payload=text_payload,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_409_CONFLICT if "exists" in detail.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc

    api_key.quota = max(0, api_key.quota - 1)
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    response = registration_service.build_proof_response(result.proof, result.matches, result.artifact)
    queue_event(
        current_user.id,
        payload.webhook_event or "ai.proof.generated",
        {
            "proof_id": str(result.proof.id),
            "model": payload.model_name,
            "prompt": payload.prompt,
        },
    )
    return schemas.ProofResponse(**response)


__all__ = ["router"]
