"""High level helpers for registering and verifying proofs."""
from __future__ import annotations

import hashlib
import json
import tempfile
import uuid
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy.orm import Session

from prooforigin.core import models
from prooforigin.core.logging import get_logger
from prooforigin.core.metadata import validate_metadata
from prooforigin.core.security import (
    decrypt_private_key,
    export_public_key,
    sign_hash,
)
from prooforigin.core.settings import Settings, get_settings
from prooforigin.services.c2pa import C2PAService, C2PAManifestContext
from prooforigin.services.ledger import LedgerReceipt, TransparencyLedger
from prooforigin.services.onchain import (
    OnChainConfigurationError,
    OpenTimestampsAnchor,
    PolygonAnchor,
)
from prooforigin.services.pipeline import NormalizationPipeline
from prooforigin.services.similarity import SimilarityEngine
from prooforigin.services.storage import get_storage_service
from prooforigin.services.timestamp import TimestampAuthority
from prooforigin.services.webhooks import queue_event
from prooforigin.tasks.queue import get_task_queue

logger = get_logger(__name__)


@dataclass(slots=True)
class ProofContent:
    data: bytes
    filename: str
    mime_type: str | None
    is_binary: bool = True


@dataclass(slots=True)
class ProofCreationResult:
    proof: models.Proof
    matches: list[dict[str, Any]]
    artifact: dict[str, Any]


class ProofRegistrationService:
    """Encapsulate the business logic to register proofs."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.similarity_engine = SimilarityEngine(self.settings)
        self.storage_service = get_storage_service()
        self.task_queue = get_task_queue()
        self.timestamp_authority = TimestampAuthority(self.settings)
        self.onchain_anchor = PolygonAnchor(self.settings)
        self.open_timestamp_anchor = OpenTimestampsAnchor(self.settings)
        self.pipeline = NormalizationPipeline(self.settings)
        self.c2pa = C2PAService(self.settings)
        self.ledger = TransparencyLedger(self.settings)

    # ------------------------------------------------------------------
    def _parse_metadata(self, metadata_raw: str | None) -> dict[str, Any]:
        if not metadata_raw:
            return {}
        try:
            return validate_metadata(json.loads(metadata_raw))
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid metadata JSON") from exc

    def _assign_to_anchor_batch(self, db: Session, proof: models.Proof) -> None:
        batch = (
            db.query(models.AnchorBatch)
            .filter(models.AnchorBatch.status == "pending")
            .order_by(models.AnchorBatch.created_at.asc())
            .first()
        )
        if batch is None or len(batch.proofs) >= self.settings.anchor_batch_size:
            batch = models.AnchorBatch(merkle_root=uuid.uuid4().hex)
            db.add(batch)
            db.flush()
        proof.anchor_batch_id = batch.id

    def _persist_original_file(
        self,
        proof: models.Proof,
        db: Session,
        file_bytes: bytes,
        filename: str,
        mime_type: str | None,
    ) -> None:
        storage_ref = self.storage_service.store(BytesIO(file_bytes), filename=filename)
        db.add(
            models.ProofFile(
                proof_id=proof.id,
                filename=filename,
                mime=mime_type,
                size=len(file_bytes),
                storage_ref=storage_ref,
            )
        )

    def _persist_artifact(
        self,
        proof: models.Proof,
        user: models.User,
        metadata_payload: dict[str, Any],
        signature: str,
        db: Session,
    ) -> dict[str, Any]:
        artifact = {
            "prooforigin_protocol": "POP-1.0",
            "proof_id": str(proof.id),
            "hash": {"algorithm": "SHA-256", "value": proof.file_hash},
            "normalized_hash": {"algorithm": "SHA-256", "value": proof.normalized_hash},
            "signature": {"algorithm": "Ed25519", "value": signature},
            "public_key": export_public_key(user.public_key),
            "timestamp": proof.created_at.isoformat(),
            "metadata": metadata_payload,
        }
        artifact_bytes = json.dumps(artifact, ensure_ascii=False, indent=2).encode("utf-8")
        artifact_ref = self.storage_service.store(artifact_bytes, filename=f"{proof.id}.proof.json")
        db.add(
            models.ProofFile(
                proof_id=proof.id,
                filename=Path(artifact_ref).name,
                mime="application/json",
                size=len(artifact_bytes),
                storage_ref=artifact_ref,
            )
        )
        return artifact

    def _persist_normalized_file(
        self,
        proof: models.Proof,
        db: Session,
        normalized_bytes: bytes,
        normalized_extension: str,
        normalized_mime: str,
    ) -> str:
        filename = f"{proof.id}.normalized.{normalized_extension}"
        storage_ref = self.storage_service.store(normalized_bytes, filename=filename)
        db.add(
            models.ProofFile(
                proof_id=proof.id,
                filename=filename,
                mime=normalized_mime,
                size=len(normalized_bytes),
                storage_ref=storage_ref,
            )
        )
        return storage_ref

    def _persist_fingerprints(
        self,
        proof: models.Proof,
        db: Session,
        normalized_hash: str,
        phash: str | None,
        dhash: str | None,
        perceptual_vector: list[float] | None,
    ) -> None:
        db.query(models.AssetFingerprint).filter(models.AssetFingerprint.proof_id == proof.id).delete()
        db.add(
            models.AssetFingerprint(
                proof_id=proof.id,
                fingerprint_type="sha256",
                value=normalized_hash,
            )
        )
        if phash:
            db.add(
                models.AssetFingerprint(
                    proof_id=proof.id,
                    fingerprint_type="phash",
                    value=phash,
                    vector=perceptual_vector,
                )
            )
        if dhash:
            db.add(
                models.AssetFingerprint(
                    proof_id=proof.id,
                    fingerprint_type="dhash",
                    value=dhash,
                )
            )
        db.flush()

    def _record_usage_meter(self, db: Session, user: models.User, action: str) -> None:
        meter = (
            db.query(models.UsageMeter)
            .filter(models.UsageMeter.user_id == user.id)
            .filter(models.UsageMeter.metered_action == action)
            .order_by(models.UsageMeter.window_start.desc())
            .first()
        )
        if meter and meter.window_end is None:
            meter.quantity += 1
        else:
            db.add(
                models.UsageMeter(
                    user_id=user.id,
                    metered_action=action,
                    quantity=1,
                )
            )

    def _calculate_risk_score(
        self,
        proof: models.Proof,
        matches: list[dict[str, Any]],
        normalized_warnings: list[str],
        manifest_present: bool,
    ) -> int:
        score = 0
        if normalized_warnings:
            score += min(20, 5 * len(normalized_warnings))
        if not manifest_present:
            score += 30
        if not proof.blockchain_tx:
            score += 25
        high_match = any(float(match.get("score", 0.0)) >= 0.9 for match in matches)
        if high_match:
            score += 30
        return min(score, 100)

    def _compute_embeddings(
        self,
        tmp_path: Path | None,
        metadata_payload: dict[str, Any],
        text_payload: str | None,
    ) -> tuple[list[float] | None, list[float] | None]:
        metadata_text = " ".join(
            filter(
                None,
                [
                    metadata_payload.get("title"),
                    metadata_payload.get("description"),
                    " ".join(metadata_payload.get("tags", [])) if metadata_payload.get("tags") else None,
                ],
            )
        )
        combined_text = " ".join(filter(None, [metadata_text, text_payload]))
        text_embedding = self.similarity_engine.compute_text_embedding(combined_text)
        clip_vector = None
        if tmp_path and tmp_path.exists():
            _, _, _, clip_vector = self.similarity_engine.compute_image_hashes(tmp_path)
        return clip_vector, text_embedding

    def _record_usage(self, user: models.User, proof: models.Proof, db: Session) -> None:
        user.credits = max(0, user.credits - 1)
        db.add(
            models.UsageLog(
                user_id=user.id,
                action="generate_proof",
                metadata_json={"proof_id": str(proof.id)},
            )
        )

    # ------------------------------------------------------------------
    def register_content(
        self,
        db: Session,
        user: models.User,
        content: ProofContent,
        metadata_raw: str | None,
        key_password: str,
        text_payload: str | None = None,
    ) -> ProofCreationResult:
        metadata_payload = self._parse_metadata(metadata_raw)
        normalized_asset = self.pipeline.normalize(content)
        file_hash = normalized_asset.normalized_hash

        if db.query(models.Proof).filter(models.Proof.file_hash == file_hash).first():
            raise ValueError("Proof already exists")

        try:
            private_key = decrypt_private_key(
                user.encrypted_private_key,
                user.private_key_nonce,
                user.private_key_salt,
                key_password,
            )
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError("Unable to decrypt private key") from exc

        signature = sign_hash(file_hash, private_key)

        tmp_file: Path | None = None
        normalized_tmp: Path | None
        if content.is_binary:
            raw_tmp = tempfile.NamedTemporaryFile(delete=False)
            try:
                raw_tmp.write(content.data)
            finally:
                raw_tmp.close()
            tmp_file = Path(raw_tmp.name)
        normalized_handle = tempfile.NamedTemporaryFile(delete=False)
        try:
            normalized_handle.write(normalized_asset.normalized_bytes)
        finally:
            normalized_handle.close()
        normalized_tmp = Path(normalized_handle.name)

        clip_vector, text_embedding = self._compute_embeddings(
            normalized_tmp,
            metadata_payload,
            text_payload,
        )

        phash = normalized_asset.phash
        dhash = normalized_asset.dhash
        perceptual_vector = normalized_asset.perceptual_vector
        if normalized_tmp:
            alt_phash, alt_dhash, alt_vector, alt_clip = self.similarity_engine.compute_image_hashes(normalized_tmp)
            clip_vector = clip_vector or alt_clip
            phash = phash or alt_phash
            dhash = dhash or alt_dhash
            perceptual_vector = perceptual_vector or alt_vector

        proof = models.Proof(
            user_id=user.id,
            file_hash=file_hash,
            normalized_hash=file_hash,
            signature=signature,
            metadata_json=metadata_payload,
            file_name=content.filename,
            mime_type=content.mime_type,
            file_size=len(content.data),
            phash=phash,
            dhash=dhash,
            image_embedding=clip_vector,
            text_embedding=text_embedding,
            pipeline_version=self.settings.pipeline_version,
        )
        db.add(proof)
        db.flush()

        if self.onchain_anchor.is_configured:
            try:
                anchor_result = self.onchain_anchor.anchor_hash(file_hash)
            except OnChainConfigurationError as exc:
                logger.warning("onchain_configuration_error", error=str(exc))
            except Exception as exc:  # pragma: no cover - external dependency
                logger.error("onchain_anchor_failed", error=str(exc))
            else:
                proof.blockchain_tx = anchor_result.transaction_hash
                proof.anchor_signature = anchor_result.anchor_signature
                proof.anchored_at = anchor_result.anchored_at
                queue_event(
                    user.id,
                    "proof.anchored",
                    {
                        "proof_id": str(proof.id),
                        "transaction_hash": anchor_result.transaction_hash,
                        "anchored_at": anchor_result.anchored_at.isoformat(),
                    },
                )
        ots_receipt = None
        if "opentimestamps" in self.settings.multi_anchor_targets:
            ots_result = self.open_timestamp_anchor.anchor_hash(file_hash)
            if ots_result:
                proof.opentimestamps_receipt = ots_result.receipt
                ots_receipt = LedgerReceipt(
                    chain="opentimestamps",
                    transaction_hash=ots_result.receipt.get("ots_receipt"),
                    anchored_at=ots_result.anchored_at,
                    payload=ots_result.receipt,
                )

        receipts: list[LedgerReceipt] = []
        if proof.blockchain_tx:
            receipts.append(
                LedgerReceipt(
                    chain="polygon",
                    transaction_hash=proof.blockchain_tx,
                    anchored_at=proof.anchored_at,
                    payload={
                        "signature": proof.anchor_signature,
                        "batch": str(proof.anchor_batch_id) if proof.anchor_batch_id else None,
                    },
                )
            )
        if ots_receipt:
            receipts.append(ots_receipt)

        if not proof.blockchain_tx:
            self._assign_to_anchor_batch(db, proof)
            self.timestamp_authority.prepare_anchor(db, proof, self.task_queue)
        self._persist_original_file(proof, db, content.data, content.filename, content.mime_type)
        artifact = self._persist_artifact(proof, user, metadata_payload, signature, db)
        self._persist_fingerprints(
            proof,
            db,
            normalized_asset.normalized_hash,
            phash,
            dhash,
            perceptual_vector,
        )
        self._record_usage(user, proof, db)
        self.similarity_engine.persist_embeddings(db, proof, perceptual_vector)
        matches = self.similarity_engine.update_similarity_matches(db, proof)

        merkle_leaf = hashlib.sha256(bytes.fromhex(file_hash)).hexdigest()
        merkle_root = merkle_leaf
        ledger_entry = self.ledger.append(
            db,
            proof,
            normalized_asset.normalized_hash,
            merkle_root,
            merkle_leaf,
            receipts,
        )
        ledger_payload = self.ledger.build_receipt_json(proof, ledger_entry)
        _, manifest_ref = self.c2pa.embed(
            normalized_tmp,
            C2PAManifestContext(
                proof_id=str(proof.id),
                normalized_hash=file_hash,
                signature=signature,
                metadata=metadata_payload,
                ledger_entry=ledger_payload["ledger"],
                receipts=ledger_payload["blockchain_receipts"],
            ),
        )
        proof.c2pa_manifest_ref = manifest_ref

        final_normalized_bytes = (
            normalized_tmp.read_bytes()
            if normalized_tmp and normalized_tmp.exists()
            else normalized_asset.normalized_bytes
        )
        self._persist_normalized_file(
            proof,
            db,
            final_normalized_bytes,
            normalized_asset.normalized_extension,
            normalized_asset.normalized_mime,
        )

        proof.risk_score = self._calculate_risk_score(
            proof,
            matches,
            normalized_asset.warnings,
            manifest_present=bool(manifest_ref),
        )
        self._record_usage_meter(db, user, "proofs")

        db.commit()
        db.refresh(proof)

        for temp in filter(None, [tmp_file, normalized_tmp]):
            try:
                temp.unlink()
            except FileNotFoundError:
                pass

        self.task_queue.enqueue("prooforigin.reindex_similarity", str(proof.id))
        queue_event(
            user.id,
            "proof.generated",
            {
                "proof_id": str(proof.id),
                "file_hash": proof.file_hash,
                "created_at": proof.created_at.isoformat(),
            },
        )

        return ProofCreationResult(proof=proof, matches=matches, artifact=artifact)

    # ------------------------------------------------------------------
    def verify_hash(
        self,
        db: Session,
        file_hash: str,
    ) -> tuple[models.Proof | None, models.User | None]:
        proof = db.query(models.Proof).filter(models.Proof.file_hash == file_hash).first()
        owner: models.User | None = None
        if proof:
            owner = db.get(models.User, proof.user_id)
        return proof, owner

    def build_proof_response(
        self,
        proof: models.Proof,
        matches: Iterable[dict[str, Any]],
        artifact: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "id": proof.id,
            "file_hash": proof.file_hash,
            "normalized_hash": proof.normalized_hash,
            "signature": proof.signature,
            "metadata": proof.metadata_json,
            "anchored_at": proof.anchored_at,
            "blockchain_tx": proof.blockchain_tx,
            "created_at": proof.created_at,
            "file_name": proof.file_name,
            "mime_type": proof.mime_type,
            "file_size": proof.file_size,
            "matches": list(matches),
            "proof_artifact": artifact,
            "anchor_batch_id": proof.anchor_batch_id,
            "pipeline_version": proof.pipeline_version,
            "risk_score": proof.risk_score,
            "ledger": self.ledger.build_receipt_json(proof, proof.ledger_entry)
            if proof.ledger_entry
            else None,
            "c2pa_manifest_ref": proof.c2pa_manifest_ref,
            "opentimestamps_receipt": proof.opentimestamps_receipt,
        }


__all__ = ["ProofRegistrationService", "ProofContent", "ProofCreationResult"]
