"""ProofOrigin Python SDK with portable proof helpers."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import requests


@dataclass(slots=True)
class ZeroTrustReport:
    computed_hash: str
    matches_ledger: Optional[bool]
    matches_manifest: Optional[bool]
    ledger: Dict[str, Any] | None
    manifest: Dict[str, Any] | None


class ProofOriginClient:
    """High-level client for the ProofOrigin v1 API."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {api_key}", "Accept": "application/json"})

    # ------------------------------------------------------------------
    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.session.post(f"{self.base_url}{path}", json=payload, timeout=30)
        response.raise_for_status()
        return response.json()

    def _get(self, path: str) -> dict[str, Any]:
        response = self.session.get(f"{self.base_url}{path}", timeout=30)
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    def generate_proof(
        self,
        file_path: str | Path,
        *,
        key_password: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        path = Path(file_path)
        payload = {
            "content": base64.b64encode(path.read_bytes()).decode(),
            "filename": path.name,
            "mime_type": "application/octet-stream",
            "metadata": metadata,
            "key_password": key_password,
        }
        return self._post("/api/v1/proof", payload)

    def verify_hash(self, file_hash: str) -> dict[str, Any]:
        return self._get(f"/api/v1/verify/{file_hash}")

    def get_proof(self, proof_id: str) -> dict[str, Any]:
        return self._get(f"/api/v1/proofs/{proof_id}")

    def list_proofs(self, *, page: int = 1, page_size: int = 25) -> dict[str, Any]:
        response = self.session.get(
            f"{self.base_url}/api/v1/proofs",
            params={"page": page, "page_size": page_size},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def request_anchor(self, proof_id: str) -> dict[str, Any]:
        return self._post(f"/api/v1/anchor/{proof_id}", {})

    def similarity_search(self, *, text: str, top_k: int = 5) -> list[dict[str, Any]]:
        response = self._post(
            "/api/v1/similarity",
            {"text": text, "top_k": top_k},
        )
        if isinstance(response, list):
            return response
        return []

    def fetch_manifest(self, file_hash: str) -> dict[str, Any]:
        return self._get(f"/verify/{file_hash}/manifest")

    def fetch_ledger(self, file_hash: str) -> dict[str, Any]:
        status = self._get(f"/verify/{file_hash}")
        ledger = status.get("ledger")
        if not ledger:
            raise ValueError("Ledger entry not yet available")
        return ledger

    # ------------------------------------------------------------------
    @staticmethod
    def compute_sha256(data: bytes) -> str:
        import hashlib

        return hashlib.sha256(data).hexdigest()

    @classmethod
    def zero_trust_verify(
        cls,
        *,
        asset_path: str | Path,
        manifest: dict[str, Any] | None,
        ledger: dict[str, Any] | None,
    ) -> ZeroTrustReport:
        payload = Path(asset_path).read_bytes()
        computed_hash = cls.compute_sha256(payload)
        normalized_hash = ledger.get("normalized_hash") if ledger else None
        manifest_hash = manifest.get("proof", {}).get("hash") if manifest else None
        return ZeroTrustReport(
            computed_hash=computed_hash,
            matches_ledger=(normalized_hash == computed_hash) if normalized_hash else None,
            matches_manifest=(manifest_hash == computed_hash) if manifest_hash else None,
            ledger=ledger,
            manifest=manifest,
        )


__all__ = ["ProofOriginClient", "ZeroTrustReport"]
