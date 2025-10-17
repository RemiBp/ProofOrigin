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


def compute_merkle_root(leaves: list[str]) -> str:
    if not leaves:
        return hashlib.sha256(b"").hexdigest()
    nodes = [hashlib.sha256(leaf.encode()).hexdigest() for leaf in leaves]
    while len(nodes) > 1:
        if len(nodes) % 2 == 1:
            nodes.append(nodes[-1])
        nodes = [
            hashlib.sha256((nodes[i] + nodes[i + 1]).encode()).hexdigest()
            for i in range(0, len(nodes), 2)
        ]
    return nodes[0]


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

    def anchor_payload(self, payload: str) -> dict[str, str | datetime]:
        anchor_signature = self.sign_anchor(payload)
        tx_hash = self.submit_transaction(anchor_signature)
        return {
            "transaction_hash": tx_hash,
            "anchor_signature": anchor_signature,
            "anchored_at": datetime.utcnow(),
        }

    def anchor_proof(self, proof: models.Proof) -> dict[str, str | datetime]:
        payload = f"{proof.id}:{proof.file_hash}:{proof.created_at.isoformat()}"
        return self.anchor_payload(payload)


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
        batch = proof.anchor_batch
        proofs_to_anchor = list(batch.proofs) if batch else [proof]
        merkle_root = compute_merkle_root([p.file_hash for p in proofs_to_anchor])
        result = anchor.anchor_payload(f"merkle:{merkle_root}")
        anchored_at = result["anchored_at"]
        for batch_proof in proofs_to_anchor:
            batch_proof.blockchain_tx = result["transaction_hash"]
            batch_proof.anchor_signature = result["anchor_signature"]
            batch_proof.anchored_at = anchored_at
            session.add(batch_proof)
        if batch:
            batch.merkle_root = merkle_root
            batch.transaction_hash = result["transaction_hash"]
            batch.anchored_at = anchored_at
            batch.status = "anchored"
            session.add(batch)
        logger.info(
            "proof_anchored",
            proof_id=str(proof_id),
            tx=result["transaction_hash"],
            merkle_root=merkle_root,
        )


__all__ = ["BlockchainAnchor", "schedule_anchor", "compute_merkle_root"]
