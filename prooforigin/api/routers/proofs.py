"""Proof management routes."""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
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
from prooforigin.services.similarity import SimilarityEngine

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["proofs"])
settings = get_settings()
similarity_engine = SimilarityEngine(settings)


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
        return json.loads(metadata_raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid metadata JSON") from exc


def _user_can_spend(user: models.User) -> None:
    if user.credits <= 0:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient credits")


def _schedule_anchor_task(background_tasks: BackgroundTasks, proof_id: uuid.UUID) -> None:
    if not settings.blockchain_enabled:
        return

    from prooforigin.services.blockchain import schedule_anchor

    background_tasks.add_task(schedule_anchor, proof_id)


@router.post("/generate_proof", response_model=schemas.ProofResponse)
async def generate_proof(
    background_tasks: BackgroundTasks,
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
    image_vector = None
    text_embedding = similarity_engine.compute_text_embedding(text_content)
    phash, dhash, image_vector = similarity_engine.compute_image_hashes(temp_path)

    proof = models.Proof(
        user_id=current_user.id,
        file_hash=file_hash,
        signature=signature,
        metadata=metadata_payload,
        file_name=file.filename,
        mime_type=file.content_type,
        file_size=len(file_bytes),
        phash=phash,
        dhash=dhash,
        image_embedding=image_vector,
        text_embedding=text_embedding,
    )
    db.add(proof)
    db.flush()

    storage_dir = settings.data_dir / "storage" / str(proof.id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    stored_path = storage_dir / (file.filename or f"proof-{proof.id}")
    shutil.move(str(temp_path), stored_path)

    db.add(
        models.ProofFile(
            proof_id=proof.id,
            filename=file.filename or stored_path.name,
            mime=file.content_type,
            size=len(file_bytes),
            storage_ref=str(stored_path),
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
    artifact_path = storage_dir / f"{stored_path.stem}.proof.json"
    artifact_path.write_text(json.dumps(proof_artifact, ensure_ascii=False, indent=2))

    db.add(
        models.ProofFile(
            proof_id=proof.id,
            filename=artifact_path.name,
            mime="application/json",
            size=artifact_path.stat().st_size,
            storage_ref=str(artifact_path),
        )
    )
    current_user.credits = max(0, current_user.credits - 1)
    db.add(models.UsageLog(user_id=current_user.id, action="generate_proof", metadata={"proof_id": str(proof.id)}))

    matches = similarity_engine.update_similarity_matches(db, proof)

    db.commit()
    db.refresh(proof)

    _schedule_anchor_task(background_tasks, proof.id)

    return schemas.ProofResponse(
        id=proof.id,
        file_hash=proof.file_hash,
        signature=proof.signature,
        metadata=proof.metadata,
        anchored_at=proof.anchored_at,
        blockchain_tx=proof.blockchain_tx,
        created_at=proof.created_at,
        file_name=proof.file_name,
        mime_type=proof.mime_type,
        file_size=proof.file_size,
        matches=matches,
        proof_artifact=proof_artifact,
    )


@router.post("/verify_proof", response_model=schemas.VerifyResult)
def verify_proof(
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
            metadata={"proof_id": str(proof.id)},
        )
    )
    db.commit()

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
            metadata={"proof_id": str(proof.id)},
        )
    )
    db.commit()

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
            metadata=proof.metadata,
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
        metadata=proof.metadata,
        anchored_at=proof.anchored_at,
        blockchain_tx=proof.blockchain_tx,
        created_at=proof.created_at,
        file_name=proof.file_name,
        mime_type=proof.mime_type,
        file_size=proof.file_size,
        matches=matches,
    )


@router.post("/search-similar")
async def search_similar(
    payload: Annotated[schemas.SimilarityRequest, Body(embed=True)],
    file: UploadFile | None = File(default=None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    query = db.query(models.Proof).filter(models.Proof.user_id == current_user.id)
    candidate_proofs = query.all()

    phash = dhash = None
    image_vector = None
    text_embedding = None

    if file:
        temp_path = _save_upload_to_temp(file)
        phash, dhash, image_vector = similarity_engine.compute_image_hashes(temp_path)

    if payload.text:
        text_embedding = similarity_engine.compute_text_embedding(payload.text)

    dummy_proof = models.Proof(
        id=uuid.uuid4(),
        user_id=current_user.id,
        file_hash="",
        signature="",
        phash=phash,
        dhash=dhash,
        image_embedding=image_vector,
        text_embedding=text_embedding,
    )

    return similarity_engine.build_similarity_payload(dummy_proof, candidate_proofs, top_k=payload.top_k)


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

    return schemas.BatchVerifyResponse(job_id=job.id, status=job.status)


@router.post("/report", response_model=schemas.ReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: schemas.ReportRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.ReportResponse:
    report = models.Report(
        user_id=current_user.id,
        proof_id=payload.proof_id,
        match_id=payload.match_id,
        payload={"notes": payload.notes, "external_links": payload.external_links},
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return schemas.ReportResponse(id=report.id, status=report.status, created_at=report.created_at)
