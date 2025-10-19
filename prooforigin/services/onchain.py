"""On-chain anchoring helpers for Polygon compatible networks."""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from datetime import datetime

from prooforigin.core.logging import get_logger
from prooforigin.core.settings import Settings, get_settings

try:  # pragma: no cover - optional dependency already in requirements
    from eth_account import Account
    from web3 import Web3
    from web3.exceptions import TransactionNotFound
    from web3.middleware import geth_poa_middleware
except Exception:  # pragma: no cover - handled gracefully at runtime
    Account = None  # type: ignore
    TransactionNotFound = Exception  # type: ignore
    Web3 = None  # type: ignore
    geth_poa_middleware = None  # type: ignore


logger = get_logger(__name__)


class OnChainConfigurationError(RuntimeError):
    """Raised when mandatory blockchain configuration is missing."""


@dataclass(slots=True)
class OnChainAnchorResult:
    transaction_hash: str
    anchor_signature: str
    anchored_at: datetime


class PolygonAnchor:
    """Utility to push individual proof hashes to a Polygon smart contract."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._web3: Web3 | None = None
        self._account = None
        self._contract = None
        self._chain_id: int | None = None

        self.rpc_url = (
            os.getenv("INFURA_URL")
            or os.getenv("WEB3_RPC_URL")
            or self.settings.blockchain_rpc_url
        )
        self.private_key = (
            os.getenv("WALLET_PRIVATE_KEY")
            or os.getenv("WEB3_PRIVATE_KEY")
            or self.settings.blockchain_private_key
        )
        self.contract_address = (
            os.getenv("CONTRACT_ADDRESS")
            or self.settings.blockchain_contract_address
        )
        abi_raw = os.getenv("CONTRACT_ABI") or self.settings.blockchain_contract_abi
        self._chain_id = (
            int(os.getenv("WEB3_CHAIN_ID"))
            if os.getenv("WEB3_CHAIN_ID")
            else self.settings.blockchain_chain_id
        )

        if abi_raw:
            try:
                self.contract_abi = (
                    abi_raw if isinstance(abi_raw, list) else json.loads(abi_raw)
                )
            except json.JSONDecodeError as exc:  # pragma: no cover - config issue
                raise OnChainConfigurationError("Invalid CONTRACT_ABI JSON") from exc
        else:
            self.contract_abi = None

        self._connect()

    # ------------------------------------------------------------------
    def _connect(self) -> None:
        if not self.rpc_url or not self.private_key or not self.contract_address:
            return
        if Web3 is None or Account is None:
            logger.warning("onchain_web3_missing")
            return

        try:
            web3 = Web3(Web3.HTTPProvider(self.rpc_url))
        except Exception as exc:  # pragma: no cover - network failure
            logger.warning("onchain_web3_connection_failed", error=str(exc))
            return
        if geth_poa_middleware is not None:
            try:
                web3.middleware_onion.inject(geth_poa_middleware, layer=0)
            except ValueError:  # pragma: no cover - already injected
                pass

        account = Account.from_key(self.private_key)

        abi = self.contract_abi
        if not abi:
            logger.warning("onchain_contract_abi_missing")
            return

        try:
            contract = web3.eth.contract(
                address=Web3.to_checksum_address(self.contract_address),
                abi=abi,
            )
        except Exception as exc:  # pragma: no cover - invalid address/abi
            logger.warning("onchain_contract_init_failed", error=str(exc))
            return

        if self._chain_id is None:
            try:
                self._chain_id = web3.eth.chain_id
            except Exception:  # pragma: no cover - provider dependent
                self._chain_id = None

        self._web3 = web3
        self._account = account
        self._contract = contract
        logger.info(
            "onchain_connected",
            rpc=self.rpc_url,
            address=self.contract_address,
            chain_id=self._chain_id,
        )

    # ------------------------------------------------------------------
    @property
    def is_configured(self) -> bool:
        return bool(
            self.settings.blockchain_enabled
            and self._web3
            and self._account
            and self._contract
        )

    # ------------------------------------------------------------------
    def anchor_hash(self, file_hash: str) -> OnChainAnchorResult:
        if not self.is_configured:
            raise OnChainConfigurationError("Polygon anchor not fully configured")

        assert self._web3 is not None  # for mypy
        assert self._account is not None
        assert self._contract is not None

        normalized = file_hash if file_hash.startswith("0x") else f"0x{file_hash}"
        payload = Web3.to_bytes(hexstr=normalized)

        nonce = self._web3.eth.get_transaction_count(self._account.address)
        gas_price = self._web3.eth.gas_price

        transaction = self._contract.functions.recordProof(payload).build_transaction(
            {
                "from": self._account.address,
                "nonce": nonce,
                "gas": 200000,
                "gasPrice": gas_price,
                **({"chainId": self._chain_id} if self._chain_id is not None else {}),
            }
        )

        signed = self._account.sign_transaction(transaction)
        tx_hash = self._web3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = None
        try:  # pragma: no cover - depends on external network
            receipt = self._web3.eth.wait_for_transaction_receipt(tx_hash, timeout=90)
        except TransactionNotFound:
            logger.warning("onchain_receipt_timeout", tx=self._web3.to_hex(tx_hash))

        anchor_signature = signed.hash.hex()
        anchored_at = datetime.utcnow()

        if receipt is not None and getattr(receipt, "status", 0) != 1:
            logger.warning("onchain_receipt_status", tx=self._web3.to_hex(tx_hash), status=getattr(receipt, "status", 0))

        return OnChainAnchorResult(
            transaction_hash=self._web3.to_hex(tx_hash),
            anchor_signature=anchor_signature,
            anchored_at=anchored_at,
        )


try:  # optional dependency for OpenTimestamps operations
    from opentimestamps.client import Client
    from opentimestamps.core.ots import DetachedTimestampFile
    from opentimestamps.core.timestamp import Timestamp
    from opentimestamps.core.op import OpSHA256
except Exception:  # pragma: no cover - optional dependency
    Client = None  # type: ignore
    DetachedTimestampFile = None  # type: ignore
    Timestamp = None  # type: ignore
    OpSHA256 = None  # type: ignore


@dataclass(slots=True)
class OpenTimestampResult:
    receipt: dict[str, str]
    anchored_at: datetime


class OpenTimestampsAnchor:
    """Anchor a hash against the OpenTimestamps calendar."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.endpoint = (
            self.settings.opentimestamps_endpoint
            or os.getenv("OPENTIMESTAMPS_ENDPOINT")
            or "https://a.pool.opentimestamps.org"
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.endpoint)

    def anchor_hash(self, file_hash: str) -> OpenTimestampResult | None:
        if not self.is_configured:
            return None
        digest_hex = file_hash if file_hash.startswith("0x") else file_hash
        payload = bytes.fromhex(digest_hex)
        anchored_at = datetime.utcnow()

        if DetachedTimestampFile is None or Client is None:
            logger.warning("opentimestamps_dependency_missing")
            receipt = {
                "digest": digest_hex,
                "status": "simulated",
                "endpoint": self.endpoint,
            }
            return OpenTimestampResult(receipt=receipt, anchored_at=anchored_at)

        ts_file = DetachedTimestampFile(payload, OpSHA256())
        client = Client(self.endpoint)
        try:  # pragma: no cover - networked dependency
            client.submit(ts_file)
            upgrade = client.wait_upgrade(ts_file, timeout=60)
            if isinstance(upgrade, Timestamp):
                ts_file.timestamp = upgrade
        except Exception as exc:  # pragma: no cover - network failure
            logger.warning("opentimestamps_anchor_failed", error=str(exc))

        receipt_bytes = ts_file.serialize()
        receipt_b64 = base64.b64encode(receipt_bytes).decode()
        receipt = {
            "digest": digest_hex,
            "endpoint": self.endpoint,
            "ots_receipt": receipt_b64,
        }
        return OpenTimestampResult(receipt=receipt, anchored_at=anchored_at)


__all__ = [
    "PolygonAnchor",
    "OnChainAnchorResult",
    "OnChainConfigurationError",
    "OpenTimestampsAnchor",
    "OpenTimestampResult",
]

