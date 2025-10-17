"""Application configuration for ProofOrigin."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any


@dataclass
class ProofOriginConfig:
    """Default configuration values used by the Flask app.

    Values may be overridden with environment variables to simplify
    deployment on different platforms. Directories required by the
    application are created on instantiation.
    """

    base_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    instance_dir: Path = field(init=False)
    temp_dir: Path = field(init=False)
    export_dir: Path = field(init=False)
    database: str = field(init=False)
    private_key_path: str = field(init=False)
    public_key_path: str = field(init=False)
    blockchain_rpc_url: str = field(init=False)
    blockchain_private_key: str | None = field(init=False)
    blockchain_enabled: bool = field(init=False)
    similarity_image_threshold: float = field(init=False)
    similarity_text_threshold: float = field(init=False)

    def __post_init__(self) -> None:
        self.instance_dir = Path(os.getenv("PROOFORIGIN_INSTANCE", self.base_dir / "instance"))
        self.instance_dir.mkdir(parents=True, exist_ok=True)

        self.temp_dir = Path(os.getenv("PROOFORIGIN_TEMP", self.instance_dir / "tmp"))
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        self.export_dir = Path(os.getenv("PROOFORIGIN_EXPORT", self.instance_dir / "exports"))
        self.export_dir.mkdir(parents=True, exist_ok=True)

        default_database = self.instance_dir / "ledger.db"
        self.database = os.getenv("PROOFORIGIN_DATABASE", str(default_database))

        keys_dir = Path(os.getenv("PROOFORIGIN_KEYS", self.base_dir / "keys"))
        keys_dir.mkdir(parents=True, exist_ok=True)
        self.private_key_path = os.getenv("PROOFORIGIN_PRIVATE_KEY", str(keys_dir / "private.pem"))
        self.public_key_path = os.getenv("PROOFORIGIN_PUBLIC_KEY", str(keys_dir / "public.pem"))

        self.blockchain_rpc_url = os.getenv("WEB3_RPC_URL", "https://polygon-rpc.com")
        self.blockchain_private_key = os.getenv("WEB3_PRIVATE_KEY")
        self.blockchain_enabled = os.getenv("WEB3_ENABLED", "false").lower() in {"1", "true", "yes"}

        self.similarity_image_threshold = float(os.getenv("PROOFORIGIN_IMAGE_THRESHOLD", "0.8"))
        self.similarity_text_threshold = float(os.getenv("PROOFORIGIN_TEXT_THRESHOLD", "1.0"))

    def as_flask_config(self) -> Dict[str, Any]:
        """Return a dict that can be passed directly to ``app.config``."""
        return {
            "SECRET_KEY": os.getenv("PROOFORIGIN_SECRET_KEY", "prooforigin-dev"),
            "DATABASE": self.database,
            "PRIVATE_KEY_PATH": self.private_key_path,
            "PUBLIC_KEY_PATH": self.public_key_path,
            "TEMP_DIR": str(self.temp_dir),
            "EXPORT_DIR": str(self.export_dir),
            "BLOCKCHAIN_RPC_URL": self.blockchain_rpc_url,
            "BLOCKCHAIN_PRIVATE_KEY": self.blockchain_private_key,
            "BLOCKCHAIN_ENABLED": self.blockchain_enabled,
            "SIMILARITY_IMAGE_THRESHOLD": self.similarity_image_threshold,
            "SIMILARITY_TEXT_THRESHOLD": self.similarity_text_threshold,
            "JSON_SORT_KEYS": False,
        }


__all__ = ["ProofOriginConfig"]
