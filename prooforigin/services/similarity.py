"""Similarity indexing and search utilities."""
from __future__ import annotations

import uuid
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
from PIL import Image

try:  # optional dependencies
    import imagehash
except ImportError:  # pragma: no cover
    imagehash = None  # type: ignore

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover
    SentenceTransformer = None  # type: ignore

from sqlalchemy.orm import Session

from prooforigin.core import models
from prooforigin.core.logging import get_logger
from prooforigin.core.settings import Settings, get_settings

logger = get_logger(__name__)


@lru_cache()
def _load_sentence_model(model_name: str):  # pragma: no cover - heavy dependency
    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers not installed")
    return SentenceTransformer(model_name)


class SimilarityEngine:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def compute_image_hashes(self, file_path: Path) -> tuple[str | None, str | None, list[float] | None]:
        if imagehash is None:
            return None, None, None
        try:
            with Image.open(file_path) as img:
                img = img.convert("RGB")
                phash = imagehash.phash(img)
                dhash = imagehash.dhash(img)
                vector = np.array(phash.hash, dtype=np.float32).flatten().tolist()
                return str(phash), str(dhash), vector
        except Exception as exc:
            logger.warning("image_hash_failed", error=str(exc))
            return None, None, None

    def compute_text_embedding(self, text: str | None) -> Optional[list[float]]:
        if not text:
            return None
        try:
            model = _load_sentence_model(self.settings.sentence_transformer_model)
            embedding = model.encode(text, show_progress_bar=False, convert_to_numpy=True)
            return embedding.astype(float).tolist()
        except Exception as exc:  # pragma: no cover - dependent on model availability
            logger.warning("text_embedding_failed", error=str(exc))
            return None

    def cosine_similarity(self, a: Iterable[float], b: Iterable[float]) -> float:
        vec_a = np.array(list(a), dtype=np.float32)
        vec_b = np.array(list(b), dtype=np.float32)
        denom = np.linalg.norm(vec_a) * np.linalg.norm(vec_b)
        if denom == 0:
            return 0.0
        return float(np.dot(vec_a, vec_b) / denom)

    def hamming_similarity(self, hash_a: str | None, hash_b: str | None) -> float:
        if not hash_a or not hash_b:
            return 0.0
        if imagehash is not None:
            try:
                h1 = imagehash.hex_to_hash(hash_a)
                h2 = imagehash.hex_to_hash(hash_b)
                distance = h1 - h2
                return 1.0 - (distance / 64.0)
            except Exception:
                pass
        # fallback simple comparison
        length = min(len(hash_a), len(hash_b))
        if length == 0:
            return 0.0
        matches = sum(ch1 == ch2 for ch1, ch2 in zip(hash_a[:length], hash_b[:length]))
        return matches / length

    def build_similarity_payload(
        self,
        proof: models.Proof,
        existing: Iterable[models.Proof],
        top_k: int = 5,
    ) -> list[dict[str, float | str | dict[str, float]]]:
        results: list[tuple[float, models.Proof, dict[str, float]]] = []
        for other in existing:
            if other.id == proof.id:
                continue
            metrics: dict[str, float] = {}
            score_components = []
            if proof.phash and other.phash:
                phash_score = self.hamming_similarity(proof.phash, other.phash)
                metrics["phash"] = phash_score
                score_components.append(phash_score)
            if proof.text_embedding and other.text_embedding:
                text_score = self.cosine_similarity(proof.text_embedding, other.text_embedding)
                metrics["text"] = text_score
                score_components.append(text_score)
            if not score_components:
                continue
            avg_score = sum(score_components) / len(score_components)
            if avg_score > 0.5:
                results.append((avg_score, other, metrics))
        results.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                "score": round(score, 4),
                "proof_id": str(other.id),
                "filename": other.file_name,
                "metrics": metrics,
            }
            for score, other, metrics in results[:top_k]
        ]

    def update_similarity_matches(self, db: Session, proof: models.Proof, top_k: int = 5) -> list[dict[str, float | str | dict[str, float]]]:
        existing = (
            db.query(models.Proof)
            .filter(models.Proof.user_id == proof.user_id)
            .filter(models.Proof.id != proof.id)
            .all()
        )
        matches = self.build_similarity_payload(proof, existing, top_k=top_k)
        db.query(models.SimilarityMatch).filter(models.SimilarityMatch.proof_id == proof.id).delete()
        for match in matches:
            matched_id = match.get("proof_id")
            matched_uuid = uuid.UUID(matched_id) if matched_id else None
            db.add(
                models.SimilarityMatch(
                    proof_id=proof.id,
                    matched_proof_id=matched_uuid,
                    score=float(match["score"]),
                    match_type="hybrid",
                    details=match["metrics"],
                )
            )
        db.flush()
        return matches


__all__ = ["SimilarityEngine"]
