#!/usr/bin/env python3
"""Deployment helper for ProofOrigin (FastAPI version)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_FILE = PROJECT_ROOT / "deploy_config.json"


REQUIRED_PACKAGES = [
    "fastapi",
    "uvicorn",
    "sqlalchemy",
    "pydantic-settings",
    "argon2-cffi",
    "PyJWT",
    "python-multipart",
    "structlog",
    "stripe",
    "cryptography",
    "web3",
    "eth-account",
    "Pillow",
    "imagehash",
    "numpy",
    "sentence-transformers",
]


def run(command: List[str]) -> None:
    subprocess.run(command, check=True)


def install_dependencies() -> None:
    print("🔍 Vérification des dépendances Python…")
    missing: list[str] = []
    for package in REQUIRED_PACKAGES:
        try:
            __import__(package.replace("-", "_"))
            print(f"  ✅ {package}")
        except ImportError:
            missing.append(package)
            print(f"  ❌ {package}")
    if missing:
        print("📦 Installation des dépendances manquantes…")
        for package in missing:
            run([sys.executable, "-m", "pip", "install", package])
    print("✅ Dépendances Python prêtes")


def load_config() -> dict:
    if CONFIG_FILE.exists():
        with CONFIG_FILE.open() as handle:
            return json.load(handle)
    return {
        "environment": "production",
        "database_url": f"sqlite:///{(PROJECT_ROOT / 'instance' / 'ledger.db').as_posix()}",
        "blockchain": {
            "enabled": False,
            "rpc_url": "https://polygon-rpc.com",
            "private_key": None,
        },
        "stripe": {
            "api_key": None,
            "price_id": None,
        },
        "secret_key": None,
    }


def prepare_directories() -> None:
    for rel in ["instance", "instance/tmp", "instance/storage", "keys"]:
        path = PROJECT_ROOT / rel
        path.mkdir(parents=True, exist_ok=True)
        print(f"  📁 {path.relative_to(PROJECT_ROOT)}")


def initialize_database() -> None:
    print("🗄️ Initialisation de la base de données…")
    sys.path.append(str(PROJECT_ROOT))
    from prooforigin.core.database import init_database

    init_database()
    print("  ✅ Tables créées (si nécessaire)")


def write_env_file(config: dict) -> None:
    env_path = PROJECT_ROOT / ".env.deploy"
    content = [
        f"PROOFORIGIN_ENV={config.get('environment', 'production')}",
        f"PROOFORIGIN_DATABASE={config['database_url']}",
        f"PROOFORIGIN_PRIVATE_KEY_MASTER_KEY={config.get('secret_key', 'changeme-change-me-change-me!!')}",
    ]
    if config.get("blockchain", {}).get("enabled"):
        content.extend(
            [
                "PROOFORIGIN_BLOCKCHAIN_ENABLED=true",
                f"WEB3_RPC_URL={config['blockchain'].get('rpc_url')}",
                f"WEB3_PRIVATE_KEY={config['blockchain'].get('private_key', '')}",
            ]
        )
    if config.get("stripe", {}).get("api_key"):
        content.extend(
            [
                f"PROOFORIGIN_STRIPE_API_KEY={config['stripe']['api_key']}",
                f"PROOFORIGIN_STRIPE_PRICE_ID={config['stripe'].get('price_id', '')}",
            ]
        )
    env_path.write_text("\n".join(content))
    print(f"📝 Variables d'environnement écrites dans {env_path.name}")


def create_systemd_service() -> None:
    service_content = f"""[Unit]
Description=ProofOrigin FastAPI Server
After=network.target

[Service]
Type=simple
WorkingDirectory={PROJECT_ROOT}
EnvironmentFile={PROJECT_ROOT}/.env.deploy
ExecStart={sys.executable} -m uvicorn prooforigin.app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    service_path = PROJECT_ROOT / "prooforigin.service"
    service_path.write_text(service_content)
    print(f"🛠️ Fichier service systemd généré : {service_path}")
    print("💡 Copiez-le vers /etc/systemd/system/ et exécutez `systemctl enable --now prooforigin`")


def main() -> None:
    print("🚀 Déploiement ProofOrigin")
    config = load_config()
    install_dependencies()
    prepare_directories()
    initialize_database()
    write_env_file(config)
    create_systemd_service()
    print("✅ Déploiement prêt. Lancez `uvicorn prooforigin.app:app --host 0.0.0.0 --port 8000` ou utilisez le service systemd généré.")


if __name__ == "__main__":
    main()
