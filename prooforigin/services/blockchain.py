"""Blockchain anchoring helpers."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime

try:
    from eth_account import Account
    from eth_account.messages import encode_defunct
    from web3 import Web3
    from web3.middleware import geth_poa_middleware
except ImportError:  # pragma: no cover - optional dependency
    Account = None  # type: ignore
    encode_defunct = None  # type: ignore
    Web3 = None  # type: ignore
    geth_poa_middleware = None  # type: ignore

from prooforigin.core.database import session_scope
from prooforigin.core.logging import get_logger
from prooforigin.core.settings import get_settings
from prooforigin.core import models

logger = get_logger(__name__)
settings = get_settings()


class BlockchainAnchor:
    """Anchor proofs either on-chain or via deterministic simulation."""

    def __init__(self) -> None:
        self.rpc_url = settings.blockchain_rpc_url
        self.private_key = settings.blockchain_private_key
        self._web3 = None
        self._account = None
        if self.rpc_url and self.private_key and Web3 is not None:
            try:
                self._web3 = Web3(Web3.HTTPProvider(self.rpc_url))
                if geth_poa_middleware is not None:
                    try:
                        self._web3.middleware_onion.inject(geth_poa_middleware, layer=0)
                    except ValueError:
                        pass
                self._account = Account.from_key(self.private_key) if Account else None
                logger.info("web3_connected", rpc=self.rpc_url)
            except Exception as exc:  # pragma: no cover - network side effects
                logger.warning("web3_connection_failed", error=str(exc))
                self._web3 = None
                self._account = None

    def sign_anchor(self, payload: str) -> str:
        if self._account and encode_defunct is not None:
            message = encode_defunct(text=payload)
            signed = self._account.sign_message(message)
            return signed.signature.hex()
        if self.private_key:
            return hashlib.sha256(f"{payload}:{self.private_key}".encode()).hexdigest()
        return hashlib.sha256(payload.encode()).hexdigest()

    def submit_transaction(self, payload_hash: str) -> str:
        if self._web3 and self._account:
            try:  # pragma: no cover - depends on blockchain
                txn = {
                    "to": self._account.address,
                    "value": 0,
                    "gas": 21000,
                    "gasPrice": self._web3.to_wei("1", "gwei"),
                    "nonce": self._web3.eth.get_transaction_count(self._account.address),
                    "data": payload_hash.encode(),
                }
                signed = self._account.sign_transaction(txn)
                tx_hash = self._web3.eth.send_raw_transaction(signed.rawTransaction)
                receipt_hash = self._web3.to_hex(tx_hash)
                logger.info("anchor_sent", tx=receipt_hash)
                return receipt_hash
            except Exception as exc:
                logger.warning("anchor_tx_failed", error=str(exc))
        return f"simulated://{payload_hash}"

    def anchor_proof(self, proof: models.Proof) -> dict[str, str | datetime]:
        payload = f"{proof.id}:{proof.file_hash}:{proof.created_at.isoformat()}"
        anchor_signature = self.sign_anchor(payload)
        tx_hash = self.submit_transaction(anchor_signature)
        return {
            "transaction_hash": tx_hash,
            "anchor_signature": anchor_signature,
            "anchored_at": datetime.utcnow(),
        }


def schedule_anchor(proof_id: uuid.UUID) -> None:
    """Background task to anchor a proof."""
    if not settings.blockchain_enabled:
        return

    anchor = BlockchainAnchor()
    with session_scope() as session:
        proof = session.get(models.Proof, proof_id)
        if not proof:
            logger.warning("anchor_missing_proof", proof_id=str(proof_id))
            return
        result = anchor.anchor_proof(proof)
        proof.blockchain_tx = result["transaction_hash"]
        proof.anchor_signature = result["anchor_signature"]
        proof.anchored_at = result["anchored_at"]
        session.add(proof)
        logger.info("proof_anchored", proof_id=str(proof_id), tx=result["transaction_hash"])


__all__ = ["BlockchainAnchor", "schedule_anchor"]
