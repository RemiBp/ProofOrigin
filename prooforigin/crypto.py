"""Cryptographic helpers for ProofOrigin."""
from __future__ import annotations

import hashlib
from base64 import b64decode, b64encode
from functools import lru_cache
from pathlib import Path
from typing import BinaryIO

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


@lru_cache()
def load_private_key(path: str) -> rsa.RSAPrivateKey:
    """Load the RSA private key from disk."""
    private_path = Path(path)
    with private_path.open("rb") as handle:
        return serialization.load_pem_private_key(handle.read(), password=None, backend=default_backend())


@lru_cache()
def load_public_key_pem(path: str) -> str:
    """Return the PEM-encoded public key as a string."""
    public_path = Path(path)
    with public_path.open("rb") as handle:
        return handle.read().decode()


def compute_hash_from_stream(stream: BinaryIO) -> str:
    """Compute the SHA-256 hash for a file-like object and rewind it."""
    sha256 = hashlib.sha256()
    for chunk in iter(lambda: stream.read(4096), b""):
        sha256.update(chunk)
    stream.seek(0)
    return sha256.hexdigest()


def compute_hash_from_path(path: str) -> str:
    """Compute the SHA-256 hash for the file stored at ``path``."""
    sha256 = hashlib.sha256()
    file_path = Path(path)
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def sign_hash(hash_value: str, private_key_path: str) -> str:
    """Return a base64 encoded RSA-PSS signature for ``hash_value``."""
    private_key = load_private_key(private_key_path)
    signature = private_key.sign(
        bytes.fromhex(hash_value),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    return b64encode(signature).decode()


def verify_signature(hash_value: str, signature_b64: str, public_key_pem: str) -> bool:
    """Verify a base64 encoded RSA-PSS signature against ``hash_value``."""
    public_key = serialization.load_pem_public_key(public_key_pem.encode(), backend=default_backend())
    signature = b64decode(signature_b64)
    public_key.verify(
        signature,
        bytes.fromhex(hash_value),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    return True


__all__ = [
    "compute_hash_from_path",
    "compute_hash_from_stream",
    "load_private_key",
    "load_public_key_pem",
    "sign_hash",
    "verify_signature",
]
