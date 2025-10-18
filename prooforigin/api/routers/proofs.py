"""Proof management routes."""
from __future__ import annotations

from datetime import datetime

import hashlib
import json
import shutil
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
from sqlalchemy.orm import Session

from prooforigin.api import schemas
from prooforigin.api.dependencies.auth import get_current_user
from prooforigin.api.dependencies.database import get_db
from prooforigin.core import models
from prooforigin.core.logging import get_logger
from prooforigin.core.security import decrypt_private_key, export_public_key, sign_hash, verify_signature
from prooforigin.core.settings import get_settings
from prooforigin.core.metadata import validate_metadata
from prooforigin.core.rate_limiter import get_limiter
from prooforigin.services.similarity import SimilarityEngine
from prooforigin.services.storage import get_storage_service
from prooforigin.services.webhooks import queue_event
from prooforigin.tasks.queue import get_task_queue

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["proofs"])
settings = get_settings()
similarity_engine = SimilarityEngine(settings)
task_queue = get_task_queue()
storage_service = get_storage_service()
limiter = get_limiter()


def _save_upload_to_temp(upload: UploadFile) -> Path:
    tmp_dir = settings.data_dir / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, dir=tmp_dir) as tmp:
        shutil.copyfileobj(upload.file, tmp)
        temp_path = Path(tmp.name)
    upload.file.seek(0)
    return temp_path


def _parse_metadata(metadata_raw: str | None) -> dict:
    if not metadata_raw:
        return {}
    try:
        payload = json.loads(metadata_raw)
        return validate_metadata(payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid metadata JSON") from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _user_can_spend(user: models.User) -> None:
    if user.credits <= 0:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient credits")


def _schedule_anchor_task(proof_id: uuid.UUID) -> None:
    if not settings.blockchain_enabled:
        return
    task_queue.enqueue("prooforigin.anchor_proof", str(proof_id))


def _assign_to_anchor_batch(db: Session, proof: models.Proof) -> None:
    batch = (
        db.query(models.AnchorBatch)
        .filter(models.AnchorBatch.status == "pending")
        .order_by(models.AnchorBatch.created_at.asc())
        .first()
    )
    if batch is None or len(batch.proofs) >= settings.anchor_batch_size:
        batch = models.AnchorBatch(merkle_root=uuid.uuid4().hex)
        db.add(batch)
        db.flush()

    proof.anchor_batch_id = batch.id


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

    temp_path = _save_upload_to_temp(file)
    file_bytes = temp_path.read_bytes()
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    if db.query(models.Proof).filter(models.Proof.file_hash == file_hash).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Proof already exists")

    try:
        private_key = decrypt_private_key(
            current_user.encrypted_private_key,
            current_user.private_key_nonce,
            current_user.private_key_salt,
            key_password,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unable to decrypt private key") from exc

    signature = sign_hash(file_hash, private_key)
    metadata_payload = _parse_metadata(metadata)
    text_content = " ".join(
        filter(
            None,
            [
                metadata_payload.get("title"),
                metadata_payload.get("description"),
                " ".join(metadata_payload.get("tags", [])) if metadata_payload.get("tags") else None,
            ],
        )
    )

    phash = dhash = None
    perceptual_vector = None
    clip_vector = None
    text_embedding = similarity_engine.compute_text_embedding(text_content)
    phash, dhash, perceptual_vector, clip_vector = similarity_engine.compute_image_hashes(temp_path)

    proof = models.Proof(
        user_id=current_user.id,
        file_hash=file_hash,
        signature=signature,
        metadata_json=metadata_payload,
        file_name=file.filename,
        mime_type=file.content_type,
        file_size=len(file_bytes),
        phash=phash,
        dhash=dhash,
        image_embedding=clip_vector,
        text_embedding=text_embedding,
    )
    db.add(proof)
    db.flush()

    _assign_to_anchor_batch(db, proof)

    storage_ref = storage_service.store(temp_path.open("rb"), filename=file.filename)
    temp_path.unlink(missing_ok=True)

    db.add(
        models.ProofFile(
            proof_id=proof.id,
            filename=file.filename or Path(storage_ref).name,
            mime=file.content_type,
            size=len(file_bytes),
            storage_ref=storage_ref,
        )
    )

    public_key_export = export_public_key(current_user.public_key)
    proof_artifact = {
        "prooforigin_protocol": "POP-1.0",
        "proof_id": str(proof.id),
        "hash": {"algorithm": "SHA-256", "value": file_hash},
        "signature": {"algorithm": "Ed25519", "value": signature},
        "public_key": public_key_export,
        "timestamp": proof.created_at.isoformat(),
        "metadata": metadata_payload,
    }
    artifact_bytes = json.dumps(proof_artifact, ensure_ascii=False, indent=2).encode("utf-8")
    artifact_ref = storage_service.store(artifact_bytes, filename=f"{proof.id}.proof.json")

    db.add(
        models.ProofFile(
            proof_id=proof.id,
            filename=Path(artifact_ref).name,
            mime="application/json",
            size=len(artifact_bytes),
            storage_ref=artifact_ref,
        )
    )
    current_user.credits = max(0, current_user.credits - 1)
    db.add(models.UsageLog(user_id=current_user.id, action="generate_proof", metadata_json={"proof_id": str(proof.id)}))

    similarity_engine.persist_embeddings(db, proof, perceptual_vector)
    matches = similarity_engine.update_similarity_matches(db, proof)

    db.commit()
    db.refresh(proof)

    _schedule_anchor_task(proof.id)
    queue_event(
        current_user.id,
        "proof.generated",
        {
            "proof_id": str(proof.id),
            "file_hash": proof.file_hash,
            "created_at": proof.created_at.isoformat(),
        },
    )
    task_queue.enqueue("prooforigin.reindex_similarity", str(proof.id))

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
        proof_artifact=proof_artifact,
        anchor_batch_id=proof.anchor_batch_id,
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

    temp_path = _save_upload_to_temp(file)
    file_hash = hashlib.sha256(temp_path.read_bytes()).hexdigest()

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
        temp_path = _save_upload_to_temp(file)
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
