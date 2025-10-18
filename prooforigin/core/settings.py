"""Application settings for the ProofOrigin platform."""
from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralised configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="PROOFORIGIN_", case_sensitive=False)

    app_name: str = "ProofOrigin"
    environment: Literal["development", "staging", "production"] = "development"
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(48))

    # Database
    data_dir: Path = Field(default_factory=lambda: Path.cwd() / "instance")
    database_url: str | None = None

    # Security
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    password_time_cost: int = 3
    password_memory_cost: int = 64 * 1024
    password_parallelism: int = 2
    private_key_master_key: str | None = None
    secrets_backend: Literal["local", "aws_kms", "vault"] = "local"
    aws_kms_key_id: str | None = None
    aws_region: str | None = None
    kms_encrypted_master_key: str | None = None
    vault_addr: str | None = None
    vault_token: str | None = None
    vault_master_key_path: str | None = None
    hsm_library_path: str | None = None
    creator_key_device_binding: bool = True

    # Similarity / ML
    enable_faiss: bool = False
    faiss_index_path: Path = Field(
        default_factory=lambda: Path.cwd() / "instance" / "faiss.index"
    )
    sentence_transformer_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    clip_model_name: str = "sentence-transformers/clip-ViT-B-32"

    # Stripe / billing
    stripe_api_key: str | None = None
    stripe_price_id: str | None = None
    stripe_price_pro: str | None = None
    stripe_price_business: str | None = None
    stripe_webhook_secret: str | None = None
    default_credit_pack: int = 100

    # Storage
    storage_backend: Literal["local", "s3"] = "local"
    storage_local_path: Path = Field(
        default_factory=lambda: Path.cwd() / "instance" / "uploads"
    )
    storage_s3_bucket: str | None = None
    storage_s3_endpoint: str | None = None
    storage_s3_region: str | None = None
    storage_s3_access_key: str | None = None
    storage_s3_secret_key: str | None = None

    # Blockchain anchoring
    blockchain_rpc_url: str | None = None
    blockchain_private_key: str | None = None
    blockchain_chain_id: int | None = None
    blockchain_enabled: bool = False
    blockchain_contract_address: str | None = None
    blockchain_contract_abi: str | None = None
    anchor_batch_size: int = 10
    anchor_retry_limit: int = 3
    anchor_poll_interval_seconds: int = 15
    timestamp_backend: Literal["blockchain", "opentimestamps"] = "blockchain"
    opentimestamps_endpoint: str | None = None
    multi_anchor_targets: list[str] = Field(default_factory=lambda: ["polygon", "opentimestamps"])
    merkle_batch_interval_seconds: int = 30
    ledger_signing_key: str | None = None
    ledger_signing_cert: str | None = None
    transparency_log_namespace: str = "primary"

    # Task queue
    task_queue_backend: Literal["inline", "celery"] = "inline"
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    # Webhooks / notifications
    webhook_retry_max: int = 5
    webhook_retry_backoff_seconds: int = 30
    webhook_hmac_secret: str | None = None

    # Metadata validation
    metadata_schema_path: Path | None = None

    # Portable proofs / pipeline
    pipeline_target_size: int = 2048
    pipeline_version: str = "v2"
    c2pa_signing_profile: str = "ProofOrigin/1.0"
    c2pa_signing_key: str | None = None
    c2pa_signing_cert: str | None = None
    verifier_script_cdn_url: str | None = None

    # Rate limiting / monitoring
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60
    rate_limit_storage_url: str | None = None
    redis_url: str | None = None
    sentry_dsn: str | None = None
    enable_prometheus: bool = True
    metrics_namespace: str = "prooforigin"

    @property
    def resolved_database_url(self) -> str:
        """Return the configured database URL defaulting to a local SQLite file."""
        if self.database_url:
            return self.database_url

        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{(self.data_dir / 'ledger.db').as_posix()}"

    @property
    def resolved_rate_limit_storage(self) -> str:
        if self.rate_limit_storage_url:
            return self.rate_limit_storage_url
        if self.redis_url:
            return f"redis://{self.redis_url.split('://')[-1]}"
        return "memory://"

    @property
    def resolved_storage_path(self) -> Path:
        path = self.storage_local_path
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def resolved_master_key(self) -> bytes:
        """Return a 32-byte master key for private key encryption."""
        if self.private_key_master_key:
            key = self.private_key_master_key.encode()
            if len(key) < 32:
                key = key.ljust(32, b"0")
            return key[:32]
        from prooforigin.core.secrets import MasterKeyProvider  # local import to avoid cycle

        provider = MasterKeyProvider(self)
        return provider.get_master_key()


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings


__all__ = ["Settings", "get_settings"]
