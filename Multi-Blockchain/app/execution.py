"""Execution Layer (L2) client – high-throughput transaction processing.

Handles operational data: monitoring logs, sensor data streams, interim
reports, and other high-volume, low-criticality transactions.  Optimised
for low latency and high throughput at the cost of weaker finality
(guaranteed by periodic state-root anchoring to the settlement layer).

All operations degrade gracefully when the provider is unavailable.
"""

from __future__ import annotations

import importlib.util
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_WEB3_AVAILABLE = importlib.util.find_spec("web3") is not None

# ── Minimal ABI for L2 data registry ─────────────────────────

_L2_DATA_REGISTRY_ABI: List[Dict[str, Any]] = [
    {
        "name": "recordData",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "dataHash", "type": "bytes32"},
            {"name": "sender", "type": "address"},
            {"name": "category", "type": "string"},
        ],
        "outputs": [],
    },
    {
        "name": "getLatestStateRoot",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [
            {"name": "stateRoot", "type": "bytes32"},
            {"name": "blockNumber", "type": "uint256"},
        ],
    },
]


@dataclass
class L2TxReceipt:
    tx_hash: str
    block_number: int
    status: int


class ExecutionClient:
    """Client for the Layer-2 execution chain.

    Provides fast transaction submission and state-root retrieval for
    periodic anchoring to the settlement layer.
    """

    def __init__(
        self,
        provider_url: str = "",
        private_key: str = "",
        chain_id: int = 137,
    ) -> None:
        self._enabled = False
        self._w3: Any = None
        self._account: Any = None
        self._chain_id = chain_id

        if not _WEB3_AVAILABLE:
            logger.warning("web3 package not installed – execution layer disabled")
            return

        if not provider_url:
            logger.info("No L2_PROVIDER_URL – execution layer disabled")
            return

        try:
            from web3 import Web3

            self._w3 = Web3(Web3.HTTPProvider(provider_url))
            if not self._w3.is_connected():
                logger.warning("Cannot connect to L2 provider %s", provider_url)
                return

            if private_key:
                self._account = self._w3.eth.account.from_key(private_key)

            self._enabled = True
            logger.info("Execution client initialised (chain_id=%d)", chain_id)
        except Exception as exc:
            logger.warning("Execution client init failed: %s", exc)

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    # ── helpers ───────────────────────────────────────────────

    def _send_tx(self, tx_data: Dict[str, Any]) -> Optional[L2TxReceipt]:
        if not self._enabled or not self._account:
            return None
        try:
            tx_data.update(
                {
                    "from": self._account.address,
                    "nonce": self._w3.eth.get_transaction_count(self._account.address),
                    "chainId": self._chain_id,
                }
            )
            if "gas" not in tx_data:
                tx_data["gas"] = 100_000
            if "gasPrice" not in tx_data:
                tx_data["gasPrice"] = self._w3.eth.gas_price

            signed = self._account.sign_transaction(tx_data)
            tx_hash = self._w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=15)
            return L2TxReceipt(
                tx_hash=receipt.transactionHash.hex(),
                block_number=receipt.blockNumber,
                status=receipt.status,
            )
        except Exception as exc:
            logger.error("L2 tx failed: %s", exc)
            return None

    @staticmethod
    def _to_bytes32(value: str) -> bytes:
        import hashlib
        return hashlib.sha256(value.encode()).digest()

    # ── Data submission ──────────────────────────────────────

    def submit_data(
        self, payload_hash: str, sender: str, category: str = "general"
    ) -> Optional[L2TxReceipt]:
        """Submit operational data to the execution layer.

        The actual payload is stored off-chain (e.g. IPFS); only the hash
        is recorded on-chain for integrity verification.
        """
        if not self._enabled or not self._account:
            logger.info("Execution layer not available – skipping data submission")
            return None
        try:
            tx_data: Dict[str, Any] = {
                "to": self._account.address,  # self-send for data anchoring
                "value": 0,
                "data": self._w3.to_bytes(
                    hexstr=self._to_bytes32(payload_hash).hex()
                ),
            }
            return self._send_tx(tx_data)
        except Exception as exc:
            logger.error("L2 data submission failed: %s", exc)
            return None

    def get_latest_block(self) -> Optional[Dict[str, Any]]:
        """Retrieve the latest L2 block number and hash for state anchoring."""
        if not self._enabled:
            return None
        try:
            block = self._w3.eth.get_block("latest")
            return {
                "block_number": block.number,
                "block_hash": block.hash.hex(),
                "state_root": block.stateRoot.hex() if hasattr(block, "stateRoot") else "",
                "timestamp": block.timestamp,
            }
        except Exception as exc:
            logger.error("Failed to get latest L2 block: %s", exc)
            return None

    def get_transaction_count(self) -> Optional[int]:
        """Get the pending transaction count for the configured account."""
        if not self._enabled or not self._account:
            return None
        try:
            return self._w3.eth.get_transaction_count(self._account.address)
        except Exception as exc:
            logger.error("Failed to get L2 tx count: %s", exc)
            return None
