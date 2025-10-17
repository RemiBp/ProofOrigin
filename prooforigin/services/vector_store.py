"""FAISS-backed similarity index helpers."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

try:  # Optional dependency, imported lazily when available
    import faiss  # type: ignore
except ImportError:  # pragma: no cover - optional
    faiss = None  # type: ignore

from prooforigin.core.logging import get_logger

logger = get_logger(__name__)


class VectorStore:
    """Persist embeddings locally using FAISS when available."""

    def __init__(self, index_path: Path, dimension: int, metric: str = "cosine") -> None:
        self.index_path = index_path
        self.dimension = dimension
        self.metric = metric
        self._lock = threading.Lock()
        self._index = None
        self._id_map: list[str] = []
        if faiss is not None:
            self._load()
        else:
            logger.info("faiss_unavailable", path=str(index_path))

    # Internal helpers -------------------------------------------------
    def _metric_to_faiss(self) -> int:
        if self.metric == "cosine":
            return faiss.METRIC_INNER_PRODUCT  # type: ignore[attr-defined]
        return faiss.METRIC_L2  # type: ignore[attr-defined]

    def _ensure_index(self):
        if self._index is None and faiss is not None:
            if self.metric == "cosine":
                self._index = faiss.IndexFlatIP(self.dimension)  # type: ignore[attr-defined]
            else:
                self._index = faiss.IndexFlatL2(self.dimension)  # type: ignore[attr-defined]

    def _load(self) -> None:
        if faiss is None:
            return
        if self.index_path.exists():
            try:
                self._index = faiss.read_index(str(self.index_path))  # type: ignore[attr-defined]
                id_map_path = self.index_path.with_suffix(".ids")
                if id_map_path.exists():
                    self._id_map = id_map_path.read_text().splitlines()
                logger.info("faiss_index_loaded", entries=len(self._id_map))
            except Exception as exc:  # pragma: no cover - disk errors
                logger.warning("faiss_index_failed", error=str(exc))
                self.index_path.unlink(missing_ok=True)
                self.index_path.with_suffix(".ids").unlink(missing_ok=True)
                self._index = None
                self._id_map = []

    # Public API -------------------------------------------------------
    def is_available(self) -> bool:
        return faiss is not None

    def reset(self) -> None:
        if faiss is None:
            return
        with self._lock:
            self._ensure_index()
            if self._index is not None:
                self._index.reset()  # type: ignore[attr-defined]
            self._id_map = []
            self.index_path.unlink(missing_ok=True)
            self.index_path.with_suffix(".ids").unlink(missing_ok=True)

    def add_vectors(self, ids: Sequence[str], vectors: Iterable[Sequence[float]]) -> None:
        if faiss is None:
            return
        vectors_array = np.array(list(vectors), dtype="float32")
        if vectors_array.size == 0:
            return
        if vectors_array.ndim == 1:
            vectors_array = np.expand_dims(vectors_array, axis=0)
        with self._lock:
            self._ensure_index()
            if self.metric == "cosine":
                norms = np.linalg.norm(vectors_array, axis=1, keepdims=True)
                norms[norms == 0] = 1.0
                vectors_array = vectors_array / norms
            self._index.add(vectors_array)  # type: ignore[attr-defined]
            self._id_map.extend(ids)
            self._persist()

    def query(self, vector: Sequence[float], top_k: int = 5) -> list[tuple[str, float]]:
        if faiss is None:
            return []
        vec = np.array(vector, dtype="float32")
        if vec.ndim == 1:
            vec = np.expand_dims(vec, axis=0)
        if self.metric == "cosine":
            norm = np.linalg.norm(vec, axis=1, keepdims=True)
            norm[norm == 0] = 1.0
            vec = vec / norm
        with self._lock:
            if self._index is None or self._index.ntotal == 0:  # type: ignore[attr-defined]
                return []
            distances, indices = self._index.search(vec, top_k)  # type: ignore[attr-defined]
        results: list[tuple[str, float]] = []
        for idx, distance in zip(indices[0], distances[0]):
            if idx == -1 or idx >= len(self._id_map):
                continue
            score = float(distance)
            if self.metric != "cosine":
                score = 1.0 / (1.0 + score)
            results.append((self._id_map[idx], score))
        return results

    # Persistence ------------------------------------------------------
    def _persist(self) -> None:
        if faiss is None or self._index is None:
            return
        try:
            faiss.write_index(self._index, str(self.index_path))  # type: ignore[attr-defined]
            id_map_path = self.index_path.with_suffix(".ids")
            id_map_path.write_text("\n".join(self._id_map))
        except Exception as exc:  # pragma: no cover
            logger.warning("faiss_persist_failed", error=str(exc))


__all__ = ["VectorStore"]

