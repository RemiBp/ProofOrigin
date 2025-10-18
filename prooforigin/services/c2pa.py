"""C2PA manifest helpers for portable proofs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prooforigin.core.logging import get_logger
from prooforigin.core.settings import Settings, get_settings
from prooforigin.services.storage import get_storage_service

logger = get_logger(__name__)

try:  # pragma: no cover - optional dependency
    from c2pa import Ingredient, Manifest, ManifestStore
except Exception:  # pragma: no cover - library optional
    Manifest = None  # type: ignore
    ManifestStore = None  # type: ignore
    Ingredient = None  # type: ignore


@dataclass(slots=True)
class C2PAManifestContext:
    proof_id: str
    normalized_hash: str
    signature: str
    metadata: dict[str, Any]
    ledger_entry: dict[str, Any]
    receipts: list[dict[str, Any]]


class C2PAService:
    """Produce and embed C2PA manifests for assets."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.storage = get_storage_service()

    def _manifest_dict(self, ctx: C2PAManifestContext) -> dict[str, Any]:
        return {
            "@context": [
                "https://schema.c2pa.org/1.3.0/context.json",
                "https://prooforigin.io/ns/proof.json",
            ],
            "type": "ProofOriginManifest",
            "profile": self.settings.c2pa_signing_profile,
            "proof": {
                "id": ctx.proof_id,
                "hash": ctx.normalized_hash,
                "signature": ctx.signature,
                "metadata": ctx.metadata,
                "ledger": ctx.ledger_entry,
                "receipts": ctx.receipts,
            },
        }

    def create_manifest_bytes(self, ctx: C2PAManifestContext) -> bytes:
        manifest_dict = self._manifest_dict(ctx)
        return json.dumps(manifest_dict, ensure_ascii=False, indent=2).encode()

    def embed(self, asset_path: Path, ctx: C2PAManifestContext) -> tuple[bytes, str]:
        manifest_bytes = self.create_manifest_bytes(ctx)
        storage_ref = self.storage.store(manifest_bytes, filename=f"{ctx.proof_id}.c2pa.json")

        if Manifest is None or ManifestStore is None:
            logger.warning("c2pa_library_missing", asset=str(asset_path))
            return manifest_bytes, storage_ref

        try:  # pragma: no cover - depends on optional C2PA support
            manifest_store = ManifestStore()
            manifest = Manifest(manifest_store)
            manifest.label = "ProofOrigin"
            manifest.metadata = json.loads(manifest_bytes.decode())
            if Ingredient is not None:
                manifest.add_ingredient(
                    Ingredient(
                        title=str(asset_path.name),
                        description="ProofOrigin normalized asset",
                        dc_format="application/octet-stream",
                    )
                )
            manifest_store.add_manifest(manifest)
            manifest_store.save(asset_path)
        except Exception as exc:
            logger.warning("c2pa_embedding_failed", error=str(exc))
        return manifest_bytes, storage_ref

    def load_manifest(self, manifest_ref: str) -> dict[str, Any] | None:
        try:
            data = self.storage.read(manifest_ref)
        except FileNotFoundError:  # pragma: no cover - storage dependent
            logger.warning("c2pa_manifest_missing", ref=manifest_ref)
            return None
        try:
            return json.loads(data.decode())
        except Exception as exc:
            logger.warning("c2pa_manifest_parse_failed", error=str(exc))
            return None


__all__ = ["C2PAService", "C2PAManifestContext"]
