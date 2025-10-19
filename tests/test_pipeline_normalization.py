"""Regression tests for the deterministic normalization pipeline."""
from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image

from prooforigin.services.pipeline import NormalizationPipeline
from prooforigin.services.proofs import ProofContent


def _build_image(path: Path, seed: int) -> bytes:
    size = 256 + (seed % 32)
    image = Image.new("RGB", (size, size), (seed % 255, (seed * 3) % 255, (seed * 7) % 255))
    image.save(path, format="JPEG")
    return path.read_bytes()


def test_pipeline_is_deterministic(tmp_path):
    pipeline = NormalizationPipeline()
    reference_hashes: dict[int, str] = {}

    for index in range(120):
        jpeg_path = tmp_path / f"asset_{index}.jpg"
        payload = _build_image(jpeg_path, index)
        content = ProofContent(data=payload, filename=jpeg_path.name, mime_type="image/jpeg")
        normalized = pipeline.normalize(content)

        assert normalized.normalized_mime == "image/png"
        assert normalized.normalized_extension == "png"
        assert hashlib.sha256(normalized.normalized_bytes).hexdigest() == normalized.normalized_hash

        if index % 10 == 0:
            # run the pipeline twice on the same payload
            normalized_again = pipeline.normalize(content)
            assert normalized_again.normalized_hash == normalized.normalized_hash

        reference_hashes[index] = normalized.normalized_hash

    # Ensure hashes are unique across distinct inputs to minimise collisions.
    assert len(set(reference_hashes.values())) == len(reference_hashes)
