"""Storage abstraction for proof assets."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import BinaryIO

from prooforigin.core.logging import get_logger
from prooforigin.core.settings import get_settings

try:  # Optional dependency
    import boto3
    from botocore.exceptions import ClientError
except Exception:  # pragma: no cover - boto not installed
    boto3 = None  # type: ignore
    ClientError = Exception  # type: ignore

logger = get_logger(__name__)


class StorageError(RuntimeError):
    """Raised when a storage operation fails."""


class StorageService:
    """High-level helper to save and retrieve proof artifacts."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None
        if self.settings.storage_backend == "s3":
            if boto3 is None:
                raise StorageError("boto3 is required for S3 storage backend")
            if not self.settings.storage_s3_bucket:
                raise StorageError("S3 bucket must be configured")
            session = boto3.session.Session(
                aws_access_key_id=self.settings.storage_s3_access_key,
                aws_secret_access_key=self.settings.storage_s3_secret_key,
                region_name=self.settings.storage_s3_region,
            )
            self._client = session.client(
                "s3",
                endpoint_url=self.settings.storage_s3_endpoint,
            )

    def _generate_key(self, filename: str | None = None) -> str:
        suffix = Path(filename).suffix if filename else ""
        return f"proofs/{uuid.uuid4().hex}{suffix}"

    def store(self, data: bytes | BinaryIO, filename: str | None = None) -> str:
        """Persist the provided bytes in the configured backend."""
        key = self._generate_key(filename)
        if self.settings.storage_backend == "local":
            target = self.settings.resolved_storage_path / key
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(data, bytes):
                target.write_bytes(data)
            else:
                target.write_bytes(data.read())
            return str(target)

        assert self._client is not None
        body = data if isinstance(data, bytes) else data.read()
        try:
            self._client.put_object(
                Bucket=self.settings.storage_s3_bucket,
                Key=key,
                Body=body,
            )
        except ClientError as exc:  # pragma: no cover - network
            logger.error("s3_upload_failed", error=str(exc), key=key)
            raise StorageError("Failed to upload object to S3") from exc
        return key

    def get_download_url(self, storage_ref: str) -> str:
        if self.settings.storage_backend == "local":
            return Path(storage_ref).as_uri()
        assert self._client is not None
        try:
            url = self._client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.settings.storage_s3_bucket,
                    "Key": storage_ref,
                },
                ExpiresIn=900,
            )
        except ClientError as exc:  # pragma: no cover - network
            logger.error("s3_presign_failed", error=str(exc))
            raise StorageError("Failed to build download URL") from exc
        return url

    def read(self, storage_ref: str) -> bytes:
        """Retrieve the raw bytes for a stored artifact."""

        if self.settings.storage_backend == "local":
            return Path(storage_ref).read_bytes()

        assert self._client is not None
        try:
            response = self._client.get_object(
                Bucket=self.settings.storage_s3_bucket,
                Key=storage_ref,
            )
        except ClientError as exc:  # pragma: no cover - network
            error_code = (
                str(getattr(exc, "response", {}).get("Error", {}).get("Code", "")).lower()
            )
            if error_code in {"nosuchkey", "404"}:
                raise FileNotFoundError(storage_ref) from exc
            logger.error("s3_read_failed", error=str(exc), key=storage_ref)
            raise StorageError("Failed to read object from S3") from exc

        body = response.get("Body")
        return body.read() if hasattr(body, "read") else body or b""


_storage_service: StorageService | None = None


def get_storage_service() -> StorageService:
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service


__all__ = ["get_storage_service", "StorageError", "StorageService"]
