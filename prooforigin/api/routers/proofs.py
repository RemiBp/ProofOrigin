"""Proof management routes."""
from __future__ import annotations

from datetime import datetime

import hashlib
import json
import tempfile
import uuid
import zipfile
from io import BytesIO
from pathlib import Path

from typing import Annotated

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from prooforigin.api import schemas
from prooforigin.api.dependencies.auth import get_current_user
from prooforigin.api.dependencies.database import get_db
from prooforigin.core import models
from prooforigin.core.logging import get_logger
from prooforigin.core.security import verify_signature
from prooforigin.core.settings import get_settings
from prooforigin.core.rate_limiter import get_limiter
from prooforigin.services.certificates import build_certificate
from prooforigin.services.proofs import (
    ProofContent,
    ProofCreationResult,
    ProofRegistrationService,
)
from prooforigin.services.similarity import SimilarityEngine
from prooforigin.services.storage import get_storage_service
from prooforigin.services.webhooks import queue_event
from prooforigin.tasks.queue import get_task_queue

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["proofs"])
settings = get_settings()
similarity_engine = SimilarityEngine(settings)
registration_service = ProofRegistrationService(settings)
task_queue = get_task_queue()
storage_service = get_storage_service()
limiter = get_limiter()


def _user_can_spend(user: models.User) -> None:
    if user.credits <= 0:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient credits")


def _write_temp_file(data: bytes) -> Path:
    tmp_dir = settings.data_dir / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, dir=tmp_dir) as tmp:
        tmp.write(data)
        path = Path(tmp.name)
    return path


def _to_proof_response(result: ProofCreationResult) -> schemas.ProofResponse:
    payload = registration_service.build_proof_response(
        result.proof,
        result.matches,
        result.artifact,
    )
    return schemas.ProofResponse(**payload)


def _build_evidence_pack(
    proof: models.Proof,
    match: models.SimilarityMatch | None,
    report_payload: dict[str, object],
) -> str:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "proof.json",
            json.dumps(
                {
                    "proof_id": str(proof.id),
                    "file_hash": proof.file_hash,
                    "signature": proof.signature,
                    "metadata": proof.metadata_json,
                    "anchored_at": proof.anchored_at.isoformat() if proof.anchored_at else None,
                    "blockchain_tx": proof.blockchain_tx,
                    "anchor_signature": proof.anchor_signature,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        if match:
            archive.writestr(
                "similarity.json",
                json.dumps(
                    {
                        "match_id": match.id,
                        "matched_proof_id": str(match.matched_proof_id) if match.matched_proof_id else None,
                        "score": match.score,
                        "metrics": match.details or {},
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        archive.writestr(
            "report.json",
            json.dumps(report_payload, ensure_ascii=False, indent=2),
        )
    buffer.seek(0)
    return storage_service.store(buffer, filename=f"report-{uuid.uuid4().hex}.zip")


@router.post("/generate_proof", response_model=schemas.ProofResponse)
async def generate_proof(
    request: Request,
    file: UploadFile = File(...),
    metadata: str | None = Form(default=None),
    key_password: str = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.ProofResponse:
    _user_can_spend(current_user)
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty upload")

    filename = file.filename or f"upload-{uuid.uuid4().hex}"
    content = ProofContent(
        data=file_bytes,
        filename=filename,
        mime_type=file.content_type,
        is_binary=True,
    )
    try:
        result = registration_service.register_content(
            db,
            current_user,
            content,
            metadata,
            key_password,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_409_CONFLICT if "exists" in detail.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc

    return _to_proof_response(result)


@router.post("/register", response_model=schemas.ProofResponse)
async def register_creation(
    request: Request,
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    metadata: str | None = Form(default=None),
    key_password: str = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.ProofResponse:
    _user_can_spend(current_user)
    if file and text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide either a file or text payload")
    if not file and not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing proof payload")

    text_payload: str | None = text
    if file:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty upload")
        filename = file.filename or f"upload-{uuid.uuid4().hex}"
        content = ProofContent(
            data=file_bytes,
            filename=filename,
            mime_type=file.content_type,
            is_binary=True,
        )
    else:
        assert text is not None
        text_bytes = text.encode("utf-8")
        filename = f"text-{uuid.uuid4().hex}.txt"
        content = ProofContent(
            data=text_bytes,
            filename=filename,
            mime_type="text/plain",
            is_binary=False,
        )

    try:
        result = registration_service.register_content(
            db,
            current_user,
            content,
            metadata,
            key_password,
            text_payload=text_payload,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_409_CONFLICT if "exists" in detail.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc

    return _to_proof_response(result)


@router.get("/verify/{file_hash}", response_model=schemas.HashVerificationResponse)
def verify_by_hash(
    file_hash: str,
    request: Request,
    db: Session = Depends(get_db),
) -> schemas.HashVerificationResponse:
    proof, owner = registration_service.verify_hash(db, file_hash)
    verification = models.Verification(
        proof_id=proof.id if proof else None,
        hash=file_hash,
        success=proof is not None,
        requester_ip=request.client.host if request.client else None,
    )
    db.add(verification)
    if proof:
        db.add(
            models.UsageLog(
                user_id=proof.user_id,
                action="verify_hash",
                metadata_json={"proof_id": str(proof.id)},
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


@router.post("/verify_proof", response_model=schemas.VerifyResult)
def verify_proof(
    request: Request,
    payload: schemas.VerifyRequest,
    db: Session = Depends(get_db),
) -> schemas.VerifyResult:
    if not payload.proof_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="proof_id required")

    proof = db.get(models.Proof, payload.proof_id)
    if not proof:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proof not found")

    user = db.get(models.User, proof.user_id)
    public_key = user.public_key if user else None
    if not public_key:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Missing author key")

    signature = payload.signature or proof.signature
    if not signature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Signature required")

    valid_signature = verify_signature(proof.file_hash, signature, public_key)

    db.add(
        models.UsageLog(
            user_id=proof.user_id,
            action="verify_proof",
            metadata_json={"proof_id": str(proof.id)},
        )
    )
    db.add(
        models.Verification(
            proof_id=proof.id,
            hash=proof.file_hash,
            success=valid_signature,
            requester_ip=request.client.host if request.client else None,
        )
    )
    db.commit()

    queue_event(
        proof.user_id,
        "proof.verified",
        {
            "proof_id": str(proof.id),
            "verified_at": datetime.utcnow().isoformat(),
            "valid_signature": valid_signature,
        },
    )

    return schemas.VerifyResult(
        valid_signature=valid_signature,
        original_hash=proof.file_hash,
        anchored=proof.blockchain_tx is not None,
        blockchain_tx=proof.blockchain_tx,
        author_id=proof.user_id,
        timestamp=proof.created_at,
    )


@router.post("/verify_proof/file", response_model=schemas.VerifyResult)
async def verify_proof_with_file(
    request: Request,
    proof_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> schemas.VerifyResult:
    proof = db.get(models.Proof, proof_id)
    if not proof:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proof not found")

    file_bytes = await file.read()
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    if file_hash != proof.file_hash:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Hash mismatch")

    user = db.get(models.User, proof.user_id)
    public_key = user.public_key if user else None
    if not public_key:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Missing author key")

    valid_signature = verify_signature(proof.file_hash, proof.signature, public_key)

    db.add(
        models.UsageLog(
            user_id=proof.user_id,
            action="verify_proof_file",
            metadata_json={"proof_id": str(proof.id)},
        )
    )
    db.add(
        models.Verification(
            proof_id=proof.id,
            hash=proof.file_hash,
            success=valid_signature,
            requester_ip=request.client.host if request.client else None,
        )
    )
    db.commit()

    queue_event(
        proof.user_id,
        "proof.verified",
        {
            "proof_id": str(proof.id),
            "verified_at": datetime.utcnow().isoformat(),
            "valid_signature": valid_signature,
        },
    )

    return schemas.VerifyResult(
        valid_signature=valid_signature,
        original_hash=proof.file_hash,
        anchored=proof.blockchain_tx is not None,
        blockchain_tx=proof.blockchain_tx,
        author_id=proof.user_id,
        timestamp=proof.created_at,
    )


@router.get("/user/proofs", response_model=schemas.ProofListResponse)
def list_user_proofs(
    page: int = 1,
    page_size: int = 20,
    anchored: bool | None = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.ProofListResponse:
    query = db.query(models.Proof).filter(models.Proof.user_id == current_user.id)
    if anchored is not None:
        if anchored:
            query = query.filter(models.Proof.blockchain_tx.isnot(None))
        else:
            query = query.filter(models.Proof.blockchain_tx.is_(None))

    total = query.count()
    proofs = query.order_by(models.Proof.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [
        schemas.ProofResponse(
            id=proof.id,
            file_hash=proof.file_hash,
            signature=proof.signature,
            metadata=proof.metadata_json,
            anchored_at=proof.anchored_at,
            blockchain_tx=proof.blockchain_tx,
            created_at=proof.created_at,
            file_name=proof.file_name,
            mime_type=proof.mime_type,
            file_size=proof.file_size,
            matches=[
                {
                    "score": match.score,
                    "proof_id": str(match.matched_proof_id) if match.matched_proof_id else None,
                    "metrics": match.details or {},
                }
                for match in proof.matches
            ],
            anchor_batch_id=proof.anchor_batch_id,
        )
        for proof in proofs
    ]
    return schemas.ProofListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/proofs/{proof_id}", response_model=schemas.ProofResponse)
def get_proof(
    proof_id: uuid.UUID,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.ProofResponse:
    proof = db.get(models.Proof, proof_id)
    if not proof or proof.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proof not found")

    matches = [
        {
            "score": match.score,
            "proof_id": str(match.matched_proof_id) if match.matched_proof_id else None,
            "metrics": match.details or {},
        }
        for match in proof.matches
    ]

    return schemas.ProofResponse(
        id=proof.id,
        file_hash=proof.file_hash,
        signature=proof.signature,
        metadata=proof.metadata_json,
        anchored_at=proof.anchored_at,
        blockchain_tx=proof.blockchain_tx,
        created_at=proof.created_at,
        file_name=proof.file_name,
        mime_type=proof.mime_type,
        file_size=proof.file_size,
        matches=matches,
        anchor_batch_id=proof.anchor_batch_id,
    )


@router.get("/proof/{proof_id}", response_model=schemas.ProofResponse)
def get_proof_details(
    proof_id: uuid.UUID,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.ProofResponse:
    return get_proof(proof_id, current_user, db)


@router.get("/proof/{proof_id}/certificate")
def download_certificate(
    proof_id: uuid.UUID,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    proof = db.get(models.Proof, proof_id)
    if not proof or proof.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proof not found")

    pdf_bytes = build_certificate(proof, current_user)
    queue_event(
        current_user.id,
        "proof.certificate.generated",
        {"proof_id": str(proof.id), "generated_at": datetime.utcnow().isoformat()},
    )
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="proof-{proof.id}.pdf"'},
    )


@router.post("/search-similar")
async def search_similar(
    request: Request,
    payload: Annotated[schemas.SimilarityRequest, Body(embed=True)],
    file: UploadFile | None = File(default=None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    query = db.query(models.Proof).filter(models.Proof.user_id == current_user.id)
    candidate_proofs: list[models.Proof]

    phash = dhash = None
    perceptual_vector = None
    clip_vector = None
    text_embedding = None

    candidate_ids: set[uuid.UUID] = set()

    if file:
        file_bytes = await file.read()
        temp_path = _write_temp_file(file_bytes)
        phash, dhash, perceptual_vector, clip_vector = similarity_engine.compute_image_hashes(temp_path)
        temp_path.unlink(missing_ok=True)
        for candidate in similarity_engine.query_vector_store("clip", clip_vector, top_k=payload.top_k * 3):
            try:
                candidate_ids.add(uuid.UUID(candidate))
            except ValueError:
                continue

    if payload.text:
        text_embedding = similarity_engine.compute_text_embedding(payload.text)
        for candidate in similarity_engine.query_vector_store("text", text_embedding, top_k=payload.top_k * 3):
            try:
                candidate_ids.add(uuid.UUID(candidate))
            except ValueError:
                continue

    if candidate_ids:
        candidate_proofs = query.filter(models.Proof.id.in_(candidate_ids)).all()
    else:
        candidate_proofs = query.all()

    dummy_proof = models.Proof(
        id=uuid.uuid4(),
        user_id=current_user.id,
        file_hash="",
        signature="",
        phash=phash,
        dhash=dhash,
        image_embedding=clip_vector,
        text_embedding=text_embedding,
    )

    results = similarity_engine.build_similarity_payload(dummy_proof, candidate_proofs, top_k=payload.top_k)
    queue_event(
        current_user.id,
        "similarity.requested",
        {
            "proof_id": payload.proof_id and str(payload.proof_id),
            "matches": len(results),
            "requested_at": datetime.utcnow().isoformat(),
        },
    )
    return results


@router.post("/batch-verify", response_model=schemas.BatchVerifyResponse, status_code=status.HTTP_202_ACCEPTED)
def batch_verify(
    payload: schemas.BatchVerifyRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.BatchVerifyResponse:
    job = models.BatchJob(
        user_id=current_user.id,
        webhook_url=payload.webhook_url,
        total_items=len(payload.proof_ids),
        processed_items=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    queue_event(
        current_user.id,
        "batch.verify_requested",
        {
            "job_id": str(job.id),
            "proof_ids": [str(pid) for pid in payload.proof_ids],
            "requested_at": job.created_at.isoformat(),
            "webhook": payload.webhook_url,
        },
    )

    return schemas.BatchVerifyResponse(job_id=job.id, status=job.status)


@router.post("/report", response_model=schemas.ReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: schemas.ReportRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.ReportResponse:
    proof = db.get(models.Proof, payload.proof_id) if payload.proof_id else None
    match = db.get(models.SimilarityMatch, payload.match_id) if payload.match_id else None

    if proof and proof.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot report foreign proof")
    if match and match.proof_id != payload.proof_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Match does not belong to proof")

    report_payload: dict[str, object] = {
        "notes": payload.notes,
        "external_links": payload.external_links,
    }

    evidence_pack = None
    if proof:
        evidence_pack = _build_evidence_pack(proof, match, report_payload)
        report_payload["evidence_pack"] = evidence_pack

    report = models.Report(
        user_id=current_user.id,
        proof_id=payload.proof_id,
        match_id=payload.match_id,
        payload=report_payload,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    queue_event(
        current_user.id,
        "report.created",
        {
            "report_id": report.id,
            "proof_id": payload.proof_id and str(payload.proof_id),
            "match_id": payload.match_id,
            "created_at": report.created_at.isoformat(),
        },
    )
    return schemas.ReportResponse(
        id=report.id,
        status=report.status,
        created_at=report.created_at,
        evidence_pack=evidence_pack,
    )
