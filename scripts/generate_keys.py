from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

BASE_DIR = Path(__file__).resolve().parent.parent
KEYS_DIR = BASE_DIR / "keys"
KEYS_DIR.mkdir(exist_ok=True)

private_key_path = KEYS_DIR / "private.pem"
public_key_path = KEYS_DIR / "public.pem"


def main() -> None:
    """Generate a new Ed25519 key pair for ProofOrigin."""
    private_key = ed25519.Ed25519PrivateKey.generate()

    private_key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )

    public_key_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    print(f"✅ Clés Ed25519 générées : {private_key_path.name} / {public_key_path.name}")


if __name__ == "__main__":
    main()
