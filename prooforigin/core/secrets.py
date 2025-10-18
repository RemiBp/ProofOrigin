"""Secret management helpers with pluggable backends."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Optional

import boto3

try:  # optional dependency for HashiCorp Vault
    import hvac
except Exception:  # pragma: no cover - hvac is optional
    hvac = None  # type: ignore

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)

from prooforigin.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class MasterKeyProvider:
    """Retrieve a 32-byte master key from KMS/Vault/local secret stores."""

    settings: "Settings"

    def _from_local(self) -> bytes:
        candidate = os.getenv("PROOFORIGIN_MASTER_KEY_B64")
        if candidate:
            try:
                key = base64.b64decode(candidate)
                if len(key) >= 32:
                    return key[:32]
            except Exception:
                logger.warning("master_key_invalid_b64")
        dev_key = (self.settings.secret_key + "::prooforigin")[:32]
        return dev_key.encode()

    def _from_kms(self) -> Optional[bytes]:
        if not self.settings.aws_kms_key_id:
            return None
        region = self.settings.aws_region or os.getenv("AWS_REGION")
        if not region:
            return None
        kms = boto3.client("kms", region_name=region)
        ciphertext = self.settings.kms_encrypted_master_key or os.getenv(
            "KMS_ENCRYPTED_MASTER_KEY"
        )
        if not ciphertext:
            response = kms.generate_data_key(KeyId=self.settings.aws_kms_key_id, KeySpec="AES_256")
            plaintext = response.get("Plaintext")
            if not plaintext:
                return None
            return plaintext[:32]
        try:
            blob = base64.b64decode(ciphertext)
        except Exception as exc:  # pragma: no cover - configuration error
            logger.error("kms_ciphertext_decode_failed", error=str(exc))
            return None
        response = kms.decrypt(CiphertextBlob=blob)
        plaintext = response.get("Plaintext")
        if not plaintext:
            return None
        return plaintext[:32]

    def _from_vault(self) -> Optional[bytes]:
        if hvac is None:
            logger.warning("vault_dependency_missing")
            return None
        if not self.settings.vault_addr or not self.settings.vault_token:
            return None
        client = hvac.Client(url=self.settings.vault_addr, token=self.settings.vault_token)
        if not client.is_authenticated():  # pragma: no cover - depends on Vault availability
            logger.error("vault_auth_failed")
            return None
        path = self.settings.vault_master_key_path or "secret/data/prooforigin/master"
        try:
            secret = client.secrets.kv.v2.read_secret_version(path=path)
        except Exception as exc:  # pragma: no cover - Vault errors
            logger.error("vault_read_failed", error=str(exc))
            return None
        data = secret.get("data", {}).get("data", {})
        key_b64 = data.get("master_key_b64")
        if not key_b64:
            return None
        try:
            key = base64.b64decode(key_b64)
        except Exception as exc:
            logger.error("vault_master_key_decode_failed", error=str(exc))
            return None
        if len(key) < 32:
            key = key.ljust(32, b"\0")
        return key[:32]

    def get_master_key(self) -> bytes:
        backend = (self.settings.secrets_backend or "local").lower()
        if backend == "aws_kms":
            key = self._from_kms()
            if key:
                return key
            logger.warning("kms_master_key_fallback")
        elif backend == "vault":
            key = self._from_vault()
            if key:
                return key
            logger.warning("vault_master_key_fallback")
        return self._from_local()


def derive_ledgers_signing_key(settings: "Settings") -> ed25519.Ed25519PrivateKey:
    """Derive or load the transparency log signing key."""

    if settings.ledger_signing_key:
        try:
            raw = base64.b64decode(settings.ledger_signing_key)
            return ed25519.Ed25519PrivateKey.from_private_bytes(raw)
        except Exception as exc:  # pragma: no cover - configuration issue
            logger.error("ledger_signing_key_invalid", error=str(exc))

    master_key = MasterKeyProvider(settings).get_master_key()
    digest = hashes.Hash(hashes.SHA256())
    digest.update(master_key)
    digest.update(b"prooforigin-ledger")
    seed = digest.finalize()
    return ed25519.Ed25519PrivateKey.from_private_bytes(seed[:32])


def export_private_key_pem(private_key: ed25519.Ed25519PrivateKey) -> str:
    return (
        private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption(),
        )
        .decode()
        .strip()
    )


__all__ = ["MasterKeyProvider", "derive_ledgers_signing_key", "export_private_key_pem"]
