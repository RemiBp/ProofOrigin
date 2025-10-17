"""Security helpers for ProofOrigin."""
from __future__ import annotations

import base64
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt
from argon2 import PasswordHasher
from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import ed25519

from .settings import get_settings

_hasher = PasswordHasher()
_settings = get_settings()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except Exception:
        return False


def _derive_key_material(password: str, salt: bytes) -> bytes:
    return hash_secret_raw(
        secret=password.encode(),
        salt=salt,
        time_cost=_settings.password_time_cost,
        memory_cost=_settings.password_memory_cost,
        parallelism=_settings.password_parallelism,
        hash_len=32,
        type=Type.ID,
    )


def _derive_encryption_key(password: str, salt: bytes) -> bytes:
    key_material = _derive_key_material(password, salt)
    master = _settings.resolved_master_key
    # XOR the key material with the master key for a simple combination
    return bytes(a ^ b for a, b in zip(key_material, master))


def encrypt_private_key(private_key: bytes, password: str) -> tuple[bytes, bytes, bytes]:
    salt = os.urandom(16)
    key = _derive_encryption_key(password, salt)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, private_key, None)
    return ciphertext, nonce, salt


def decrypt_private_key(ciphertext: bytes, nonce: bytes, salt: bytes, password: str) -> bytes:
    key = _derive_encryption_key(password, salt)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


def generate_ed25519_keypair() -> tuple[bytes, bytes]:
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return (
        private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        ),
        public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ),
    )


def derive_public_key(private_key_bytes: bytes) -> bytes:
    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def public_key_pem(public_key_bytes: bytes) -> str:
    public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
    return (
        public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
    )


def sign_hash(hash_value: str, private_key_bytes: bytes) -> str:
    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    signature = private_key.sign(bytes.fromhex(hash_value))
    return base64.b64encode(signature).decode()


def verify_signature(hash_value: str, signature: str, public_key_bytes: bytes) -> bool:
    public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
    try:
        public_key.verify(base64.b64decode(signature), bytes.fromhex(hash_value))
        return True
    except Exception:
        return False


def create_token(data: Dict[str, Any], expires_delta: timedelta, token_type: str) -> str:
    payload = data.copy()
    payload.update(
        {
            "exp": datetime.now(timezone.utc) + expires_delta,
            "iat": datetime.now(timezone.utc),
            "type": token_type,
            "jti": uuid.uuid4().hex,
        }
    )
    return jwt.encode(payload, _settings.secret_key, algorithm="HS256")


def create_access_token(data: Dict[str, Any]) -> str:
    expires = timedelta(minutes=_settings.access_token_expire_minutes)
    return create_token(data, expires, "access")


def create_refresh_token(data: Dict[str, Any]) -> str:
    expires = timedelta(days=_settings.refresh_token_expire_days)
    return create_token(data, expires, "refresh")


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, _settings.secret_key, algorithms=["HS256"])


def export_public_key(public_key_bytes: bytes) -> dict[str, str]:
    return {
        "public_key_pem": public_key_pem(public_key_bytes),
        "public_key_raw": base64.b64encode(public_key_bytes).decode(),
    }


__all__ = [
    "hash_password",
    "verify_password",
    "encrypt_private_key",
    "decrypt_private_key",
    "generate_ed25519_keypair",
    "derive_public_key",
    "sign_hash",
    "verify_signature",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "export_public_key",
]
