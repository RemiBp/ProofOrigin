"""Public Proof-as-a-Service endpoints backed by API keys."""
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
from prooforigin.core.plans import get_plan_details
from prooforigin.core.logging import get_logger
from prooforigin.services.proofs import ProofContent, ProofRegistrationService
from prooforigin.services.similarity import SimilarityEngine

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["public-api"])
registration_service = ProofRegistrationService()
similarity_engine = SimilarityEngine()


def _decode_payload(item: schemas.ProofSubmission) -> tuple[ProofContent, str | None]:
    if item.content:
        try:
            data = base64.b64decode(item.content)
        except Exception as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid base64 content") from exc
        filename = item.filename or f"upload-{uuid.uuid4().hex}"
        return (
            ProofContent(
                data=data,
                filename=filename,
                mime_type=item.mime_type,
                is_binary=True,
            ),
            None,
        )
    if item.text:
        data = item.text.encode("utf-8")
        filename = item.filename or f"text-{uuid.uuid4().hex}.txt"
        return (
            ProofContent(
                data=data,
                filename=filename,
                mime_type=item.mime_type or "text/plain",
                is_binary=False,
            ),
            item.text,
        )
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing content")


def _to_response(result: schemas.ProofResponse) -> schemas.ProofResponse:
    return result


@router.post("/proof", response_model=schemas.ProofResponse)
def api_register_proof(
    payload: schemas.ProofSubmission,
    api_key: models.ApiKey = Depends(get_api_key_record),
    current_user: models.User = Depends(get_api_key_user),
    db: Session = Depends(get_db),
) -> schemas.ProofResponse:
    if api_key.quota <= 0:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="API quota exceeded")

    content, text_payload = _decode_payload(payload)
    metadata_str = json.dumps(payload.metadata) if payload.metadata else None
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
    db.add(
        models.UsageLog(
            user_id=current_user.id,
            action="public_api.proof",
            metadata_json={"proof_id": str(result.proof.id)},
        )
    )
    db.commit()
    db.refresh(api_key)

    response = registration_service.build_proof_response(result.proof, result.matches, result.artifact)
    return schemas.ProofResponse(**response)


@router.get("/verify/{file_hash}", response_model=schemas.HashVerificationResponse)
def api_verify_hash(
    file_hash: str,
    requester: models.User = Depends(get_api_key_user),
    db: Session = Depends(get_db),
) -> schemas.HashVerificationResponse:
    proof, owner = registration_service.verify_hash(db, file_hash)
    verification = models.Verification(
        proof_id=proof.id if proof else None,
        hash=file_hash,
        success=proof is not None,
        requester_ip=str(requester.id),
    )
    db.add(verification)
    db.add(
        models.UsageLog(
            user_id=requester.id,
            action="public_api.verify",
            metadata_json={"hash": file_hash, "proof_id": str(proof.id) if proof else None},
        )
    )
    db.commit()
    return schemas.HashVerificationResponse(
        exists=proof is not None,
        proof_id=proof.id if proof else None,
        created_at=proof.created_at if proof else None,
        owner_id=owner.id if owner else None,
        owner_email=owner.email if owner else None,
        anchored=bool(proof.blockchain_tx) if proof else False,
        blockchain_tx=proof.blockchain_tx if proof else None,
    )


@router.post("/batch", response_model=schemas.BatchProofResponsePayload)
def api_batch_register(
    payload: schemas.BatchProofRequest,
    api_key: models.ApiKey = Depends(get_api_key_record),
    current_user: models.User = Depends(get_api_key_user),
    db: Session = Depends(get_db),
) -> schemas.BatchProofResponsePayload:
    results: list[schemas.BatchProofResult] = []
    for item in payload.items:
        submission = schemas.ProofSubmission(
            content=item.content,
            text=item.text,
            filename=item.filename,
            mime_type=item.mime_type,
            metadata=item.metadata,
            key_password=payload.key_password,
        )
        try:
            proof_response = api_register_proof(submission, api_key, current_user, db)
            results.append(schemas.BatchProofResult(success=True, proof=proof_response))
        except HTTPException as exc:
            results.append(
                schemas.BatchProofResult(
                    success=False,
                    error=str(exc.detail),
                )
            )
    db.add(
        models.UsageLog(
            user_id=current_user.id,
            action="public_api.batch",
            metadata_json={"items": len(payload.items)},
        )
    )
    db.commit()
    return schemas.BatchProofResponsePayload(results=results)


@router.get("/usage", response_model=schemas.UsageResponse)
def api_usage(
    current_user: models.User = Depends(get_api_key_user),
    db: Session = Depends(get_db),
) -> schemas.UsageResponse:
    proofs_generated = db.query(models.Proof).filter(models.Proof.user_id == current_user.id).count()
    verifications = (
        db.query(models.Verification)
        .join(models.Proof, models.Proof.id == models.Verification.proof_id)
        .filter(models.Proof.user_id == current_user.id)
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


@router.get("/proofs", response_model=schemas.ProofListResponse)
def api_list_proofs(
    current_user: models.User = Depends(get_api_key_user),
    db: Session = Depends(get_db),
    page: int = 1,
    page_size: int = 25,
) -> schemas.ProofListResponse:
    query = db.query(models.Proof).filter(models.Proof.user_id == current_user.id)
    total = query.count()
    proofs = (
        query.order_by(models.Proof.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        schemas.ProofResponse(
            **registration_service.build_proof_response(proof, proof.matches or [], None)
        )
        for proof in proofs
    ]
    return schemas.ProofListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/proofs/{proof_id}", response_model=schemas.ProofResponse)
def api_get_proof(
    proof_id: uuid.UUID,
    current_user: models.User = Depends(get_api_key_user),
    db: Session = Depends(get_db),
) -> schemas.ProofResponse:
    proof = db.get(models.Proof, proof_id)
    if not proof or proof.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proof not found")
    payload = registration_service.build_proof_response(proof, proof.matches or [], None)
    return schemas.ProofResponse(**payload)


@router.get("/proofs/{proof_id}/ledger")
def api_get_ledger(
    proof_id: uuid.UUID,
    current_user: models.User = Depends(get_api_key_user),
    db: Session = Depends(get_db),
):
    proof = db.get(models.Proof, proof_id)
    if not proof or proof.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proof not found")
    if not proof.ledger_entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ledger entry missing")
    return registration_service.ledger.build_receipt_json(proof, proof.ledger_entry)


@router.post("/anchor/{proof_id}", response_model=schemas.ProofResponse)
def api_anchor_proof(
    proof_id: uuid.UUID,
    current_user: models.User = Depends(get_api_key_user),
    db: Session = Depends(get_db),
) -> schemas.ProofResponse:
    proof = db.get(models.Proof, proof_id)
    if not proof or proof.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proof not found")
    if proof.blockchain_tx:
        payload = registration_service.build_proof_response(proof, proof.matches or [], None)
        return schemas.ProofResponse(**payload)
    registration_service.timestamp_authority.prepare_anchor(db, proof, registration_service.task_queue)
    db.add(
        models.UsageLog(
            user_id=current_user.id,
            action="public_api.anchor",
            metadata_json={"proof_id": str(proof.id)},
        )
    )
    db.commit()
    db.refresh(proof)
    payload = registration_service.build_proof_response(proof, proof.matches or [], None)
    return schemas.ProofResponse(**payload)


@router.post("/similarity")
def api_similarity(
    payload: schemas.SimilarityRequest,
    current_user: models.User = Depends(get_api_key_user),
    db: Session = Depends(get_db),
):
    proof_ids: list[str] = []
    if payload.text:
        embedding = similarity_engine.compute_text_embedding(payload.text)
        proof_ids = similarity_engine.query_vector_store("text", embedding, top_k=payload.top_k)
    if not proof_ids:
        return []
    proofs = (
        db.query(models.Proof)
        .filter(models.Proof.user_id == current_user.id)
        .filter(models.Proof.id.in_(proof_ids))
        .all()
    )
    db.add(
        models.UsageLog(
            user_id=current_user.id,
            action="public_api.similarity",
            metadata_json={"query_length": len(payload.text or ""), "results": len(proofs)},
        )
    )
    db.commit()
    return [
        registration_service.build_proof_response(proof, proof.matches or [], None)
        for proof in proofs
    ]


@router.get("/keys/current", response_model=schemas.ApiKeyResponse)
def api_current_key(api_key: models.ApiKey = Depends(get_api_key_record)) -> schemas.ApiKeyResponse:
    return schemas.ApiKeyResponse(
        id=api_key.id,
        key=api_key.key,
        quota=api_key.quota,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        plan=api_key.user.subscription_plan,
    )


__all__ = ["router"]
