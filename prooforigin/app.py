"""Flask application factory for ProofOrigin."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from flask import Flask

from .config import ProofOriginConfig
from .database import init_db
from .routes import bp as prooforigin_bp


def create_app(config: Dict[str, Any] | None = None) -> Flask:
    """Create and configure the Flask application."""
    default_config = ProofOriginConfig()
    app = Flask(__name__, template_folder="templates")
    app.config.update(default_config.as_flask_config())

    if config:
        app.config.update(config)

    private_key = Path(app.config["PRIVATE_KEY_PATH"])
    public_key = Path(app.config["PUBLIC_KEY_PATH"])
    if not private_key.exists() or not public_key.exists():
        raise FileNotFoundError(
            "RSA key pair not found. Run `python scripts/generate_keys.py` before starting the app."
        )

    init_db(app.config["DATABASE"])
    app.register_blueprint(prooforigin_bp)

    return app


__all__ = ["create_app"]
