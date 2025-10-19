"""Deterministic asset normalization before hashing."""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageOps

try:  # optional dependency for perceptual hashes
    import imagehash
except Exception:  # pragma: no cover - optional
    imagehash = None  # type: ignore

from prooforigin.core.logging import get_logger
from prooforigin.core.settings import Settings, get_settings

if TYPE_CHECKING:  # pragma: no cover - typing only
    from prooforigin.services.proofs import ProofContent

logger = get_logger(__name__)


@dataclass(slots=True)
class NormalizedAsset:
    normalized_bytes: bytes
    normalized_hash: str
    normalized_mime: str
    normalized_extension: str
    phash: str | None
    dhash: str | None
    perceptual_vector: list[float] | None
    clip_vector: list[float] | None
    warnings: list[str]


class NormalizationPipeline:
    """Perform deterministic transformations on incoming assets."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _normalize_image(self, data: bytes) -> NormalizedAsset:
        warnings: list[str] = []
        try:
            with Image.open(io.BytesIO(data)) as img:
                img = img.convert("RGB")
                img = ImageOps.exif_transpose(img)
                max_side = self.settings.pipeline_target_size
                if max(img.size) > max_side:
                    img.thumbnail((max_side, max_side), Image.LANCZOS)
                buffer = io.BytesIO()
                img.save(buffer, format="PNG", optimize=True)
                normalized_bytes = buffer.getvalue()
        except Exception as exc:
            warnings.append(f"image_normalization_failed:{exc}")
            normalized_bytes = data

        normalized_hash = hashlib.sha256(normalized_bytes).hexdigest()
        phash = dhash = None
        vector = clip_vector = None
        if imagehash is not None:
            try:
                with Image.open(io.BytesIO(normalized_bytes)) as img:
                    img = img.convert("RGB")
                    phash_obj = imagehash.phash(img)
                    dhash_obj = imagehash.dhash(img)
                    phash = str(phash_obj)
                    dhash = str(dhash_obj)
                    vector = list(phash_obj.hash.astype(float).flatten())
            except Exception as exc:
                warnings.append(f"perceptual_hash_failed:{exc}")

        return NormalizedAsset(
            normalized_bytes=normalized_bytes,
            normalized_hash=normalized_hash,
            normalized_mime="image/png",
            normalized_extension="png",
            phash=phash,
            dhash=dhash,
            perceptual_vector=vector,
            clip_vector=clip_vector,
            warnings=warnings,
        )

    def _normalize_text(self, data: bytes) -> NormalizedAsset:
        text = data.decode("utf-8", errors="ignore")
        normalized_text = "\n".join(line.strip() for line in text.splitlines()).strip()
        normalized_bytes = normalized_text.encode("utf-8")
        normalized_hash = hashlib.sha256(normalized_bytes).hexdigest()
        return NormalizedAsset(
            normalized_bytes=normalized_bytes,
            normalized_hash=normalized_hash,
            normalized_mime="text/plain;charset=utf-8",
            normalized_extension="txt",
            phash=None,
            dhash=None,
            perceptual_vector=None,
            clip_vector=None,
            warnings=[],
        )

    def normalize(self, content: "ProofContent") -> NormalizedAsset:
        mime = (content.mime_type or "application/octet-stream").lower()
        if mime.startswith("image/"):
            return self._normalize_image(content.data)
        if mime.startswith("text/"):
            return self._normalize_text(content.data)
        # fallback: no transformation
        normalized_hash = hashlib.sha256(content.data).hexdigest()
        return NormalizedAsset(
            normalized_bytes=content.data,
            normalized_hash=normalized_hash,
            normalized_mime=mime,
            normalized_extension=Path(content.filename).suffix.lstrip("."),
            phash=None,
            dhash=None,
            perceptual_vector=None,
            clip_vector=None,
            warnings=["unhandled_mime"],
        )


__all__ = ["NormalizationPipeline", "NormalizedAsset"]
