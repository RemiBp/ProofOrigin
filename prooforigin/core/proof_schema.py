"""Utilities for the portable .proof artifact schema."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Mapping

SCHEMA_VERSION = "1.1"


@dataclass(slots=True)
class ProofArtifact:
    """Normalized representation of the signed proof descriptor."""

    schema: str
    proof_id: str
    hash: Mapping[str, str]
    normalized_hash: Mapping[str, str]
    signature: Mapping[str, str]
    public_key: Mapping[str, str]
    timestamp: str
    metadata: Mapping[str, Any]
    c2pa_manifest_ref: str | None = None
    transparency_log: Mapping[str, Any] | None = None
    receipts: list[Mapping[str, Any]] | None = None

    def to_json(self) -> Mapping[str, Any]:
        payload = asdict(self)
        payload["schema_version"] = self.schema
        return payload


def build_artifact(
    *,
    proof_id: str,
    hash_hex: str,
    normalized_hash_hex: str,
    signature: str,
    public_key_pem: str,
    metadata: Mapping[str, Any],
    timestamp: datetime,
    manifest_ref: str | None,
    transparency_log: Mapping[str, Any] | None,
    receipts: list[Mapping[str, Any]] | None,
) -> ProofArtifact:
    """Create a structured artifact mapping to the C2PA manifest."""

    return ProofArtifact(
        schema=f"pop://artifact/{SCHEMA_VERSION}",
        proof_id=proof_id,
        hash={"algorithm": "SHA-256", "value": hash_hex},
        normalized_hash={"algorithm": "SHA-256", "value": normalized_hash_hex},
        signature={"algorithm": "Ed25519", "value": signature},
        public_key={"format": "PKCS8", "value": public_key_pem},
        timestamp=timestamp.isoformat(),
        metadata=dict(metadata),
        c2pa_manifest_ref=manifest_ref,
        transparency_log=transparency_log,
        receipts=receipts or [],
    )


__all__ = ["ProofArtifact", "SCHEMA_VERSION", "build_artifact"]
