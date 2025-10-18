"""Utility helpers to prepare a ProofOrigin deployment."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_FILE = PROJECT_ROOT / "deploy_config.json"


REQUIRED_PACKAGES: Sequence[str] = (
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
)


def run(command: Sequence[str]) -> None:
    """Execute a shell command and raise if it fails."""
    subprocess.run(command, check=True)


def install_dependencies(packages: Iterable[str] = REQUIRED_PACKAGES) -> None:
    """Ensure the core runtime dependencies are available."""
    print("🔍 Vérification des dépendances Python…")
    missing: list[str] = []
    for package in packages:
        module_name = package.replace("-", "_")
        try:
            __import__(module_name)
            print(f"  ✅ {package}")
        except ImportError:
            missing.append(package)
            print(f"  ❌ {package}")
    if missing:
        print("📦 Installation des dépendances manquantes…")
        run([sys.executable, "-m", "pip", "install", *missing])
    print("✅ Dépendances Python prêtes")


def load_config() -> dict[str, object]:
    """Load the deployment configuration if available."""
    if CONFIG_FILE.exists():
        with CONFIG_FILE.open(encoding="utf-8") as handle:
            return json.load(handle)
    return {
        "environment": "production",
        "database_url": f"sqlite:///{(PROJECT_ROOT / 'instance' / 'ledger.db').as_posix()}",
        "blockchain": {
            "enabled": False,
            "rpc_url": "https://polygon-rpc.com",
            "private_key": None,
            "contract_address": None,
            "contract_abi": None,
            "chain_id": 137,
        },
        "stripe": {
            "api_key": None,
            "price_id": None,
        },
        "secret_key": None,
    }


def prepare_directories() -> None:
    """Create runtime directories (instance data, keys…)."""
    for rel in ("instance", "instance/tmp", "instance/storage", "keys"):
        path = PROJECT_ROOT / rel
        path.mkdir(parents=True, exist_ok=True)
        print(f"  📁 {path.relative_to(PROJECT_ROOT)}")


def initialize_database() -> None:
    """Initialise the SQLAlchemy database using the built-in models."""
    print("🗄️ Initialisation de la base de données…")
    sys.path.append(str(PROJECT_ROOT))
    from prooforigin.core.database import init_database

    init_database()
    print("  ✅ Tables créées (si nécessaire)")


def write_env_file(config: dict[str, object]) -> None:
    """Generate a .env file with the most important configuration values."""
    env_path = PROJECT_ROOT / ".env.deploy"
    content = [
        f"PROOFORIGIN_ENVIRONMENT={config.get('environment', 'production')}",
        f"PROOFORIGIN_DATABASE_URL={config['database_url']}",
        f"PROOFORIGIN_PRIVATE_KEY_MASTER_KEY={config.get('secret_key', 'changeme-change-me-change-me!!')}",
    ]
    blockchain = config.get("blockchain", {}) or {}
    if blockchain.get("enabled"):
        content.extend(
            [
                "PROOFORIGIN_BLOCKCHAIN_ENABLED=true",
                f"WEB3_RPC_URL={blockchain.get('rpc_url', '')}",
                f"WEB3_PRIVATE_KEY={blockchain.get('private_key', '')}",
                f"CONTRACT_ADDRESS={blockchain.get('contract_address', '')}",
                f"CONTRACT_ABI={json.dumps(blockchain.get('contract_abi')) if blockchain.get('contract_abi') else ''}",
                f"WEB3_CHAIN_ID={blockchain.get('chain_id', '')}",
            ]
        )
    stripe = config.get("stripe", {}) or {}
    if stripe.get("api_key"):
        content.extend(
            [
                f"PROOFORIGIN_STRIPE_API_KEY={stripe['api_key']}",
                f"PROOFORIGIN_STRIPE_PRICE_ID={stripe.get('price_id', '')}",
            ]
        )
    env_path.write_text("\n".join(content), encoding="utf-8")
    print(f"📝 Variables d'environnement écrites dans {env_path.name}")


def create_systemd_service() -> None:
    """Generate a systemd service file for manual VM deployments."""
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
    service_path.write_text(service_content, encoding="utf-8")
    print(f"🛠️ Fichier service systemd généré : {service_path}")
    print("💡 Copiez-le vers /etc/systemd/system/ et exécutez `systemctl enable --now prooforigin`.")


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
