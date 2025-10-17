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

    # Similarity / ML
    enable_faiss: bool = False
    sentence_transformer_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Stripe / billing
    stripe_api_key: str | None = None
    stripe_price_id: str | None = None
    default_credit_pack: int = 100

    # Blockchain anchoring
    blockchain_rpc_url: str | None = None
    blockchain_private_key: str | None = None
    blockchain_enabled: bool = False

    # Rate limiting / monitoring
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    @property
    def resolved_database_url(self) -> str:
        """Return the configured database URL defaulting to a local SQLite file."""
        if self.database_url:
            return self.database_url

        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{(self.data_dir / 'ledger.db').as_posix()}"

    @property
    def resolved_master_key(self) -> bytes:
        """Return a 32-byte master key for private key encryption."""
        if self.private_key_master_key:
            key = self.private_key_master_key.encode()
            if len(key) < 32:
                key = key.ljust(32, b"0")
            return key[:32]
        # Development fallback – for production deployments this must be overridden.
        dev_key = (self.secret_key + "::prooforigin")[:32]
        return dev_key.encode()


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings


__all__ = ["Settings", "get_settings"]
