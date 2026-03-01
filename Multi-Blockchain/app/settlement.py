"""Settlement Layer (L1) client – Ethereum 2.0 / Proof-of-Stake.

Handles critical state changes: property registration, legally-significant
asset transfers, L2 state-root anchoring, and canonical identity NFT minting.
Designed for high security with economic finality guarantees via PoS slashing.

All operations degrade gracefully when the provider is unavailable.
"""

from __future__ import annotations

import importlib.util
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_WEB3_AVAILABLE = importlib.util.find_spec("web3") is not None

# ── Minimal ABIs for settlement-layer contracts ───────────────

_SETTLEMENT_ANCHOR_ABI: List[Dict[str, Any]] = [
    {
        "name": "anchorStateRoot",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "stateRoot", "type": "bytes32"},
            {"name": "l2BlockNumber", "type": "uint256"},
            {"name": "proof", "type": "bytes"},
        ],
        "outputs": [],
    },
    {
        "name": "verifyStateRoot",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "stateRoot", "type": "bytes32"}],
        "outputs": [
            {"name": "exists", "type": "bool"},
            {"name": "l2BlockNumber", "type": "uint256"},
            {"name": "anchoredAt", "type": "uint256"},
        ],
    },
    {
        "name": "anchors",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "", "type": "bytes32"}],
        "outputs": [
            {"name": "l2BlockNumber", "type": "uint256"},
            {"name": "submitter", "type": "address"},
            {"name": "anchoredAt", "type": "uint256"},
            {"name": "active", "type": "bool"},
        ],
    },
]

_IDENTITY_NFT_ABI: List[Dict[str, Any]] = [
    {
        "name": "mintIdentity",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "pufCommitment", "type": "bytes32"},
            {"name": "metadataURI", "type": "string"},
        ],
        "outputs": [{"name": "tokenId", "type": "uint256"}],
    },
    {
        "name": "verifyIdentity",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "tokenId", "type": "uint256"},
        ],
        "outputs": [
            {"name": "owner", "type": "address"},
            {"name": "pufCommitment", "type": "bytes32"},
            {"name": "active", "type": "bool"},
        ],
    },
    {
        "name": "revokeIdentity",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "outputs": [],
    },
]

_TRANSACTION_REGISTRY_ABI: List[Dict[str, Any]] = [
    {
        "name": "registerTransaction",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "txIdHash", "type": "bytes32"},
            {"name": "payloadHash", "type": "bytes32"},
            {"name": "sender", "type": "address"},
        ],
        "outputs": [],
    },
    {
        "name": "transactions",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "", "type": "bytes32"}],
        "outputs": [
            {"name": "payloadHash", "type": "bytes32"},
            {"name": "sender", "type": "address"},
            {"name": "registeredAt", "type": "uint256"},
            {"name": "exists", "type": "bool"},
        ],
    },
]


@dataclass
class TxReceipt:
    tx_hash: str
    block_number: int
    status: int  # 1 = success


class SettlementClient:
    """Client for the Ethereum L1 settlement layer.

    Provides methods for anchoring L2 state roots, minting canonical identity
    NFTs, and registering critical transactions on the settlement chain.
    """

    def __init__(
        self,
        provider_url: str = "",
        private_key: str = "",
        chain_id: int = 1,
        anchor_address: str = "",
        identity_nft_address: str = "",
        tx_registry_address: str = "",
    ) -> None:
        self._enabled = False
        self._w3: Any = None
        self._account: Any = None
        self._chain_id = chain_id
        self._anchor_contract: Any = None
        self._identity_contract: Any = None
        self._tx_registry_contract: Any = None

        if not _WEB3_AVAILABLE:
            logger.warning("web3 package not installed – settlement layer disabled")
            return

        if not provider_url:
            logger.info("No ETH_PROVIDER_URL – settlement layer disabled")
            return

        try:
            from web3 import Web3

            self._w3 = Web3(Web3.HTTPProvider(provider_url))
            if not self._w3.is_connected():
                logger.warning("Cannot connect to L1 provider %s", provider_url)
                return

            if private_key:
                self._account = self._w3.eth.account.from_key(private_key)

            if anchor_address:
                self._anchor_contract = self._w3.eth.contract(
                    address=Web3.to_checksum_address(anchor_address),
                    abi=_SETTLEMENT_ANCHOR_ABI,
                )
            if identity_nft_address:
                self._identity_contract = self._w3.eth.contract(
                    address=Web3.to_checksum_address(identity_nft_address),
                    abi=_IDENTITY_NFT_ABI,
                )
            if tx_registry_address:
                self._tx_registry_contract = self._w3.eth.contract(
                    address=Web3.to_checksum_address(tx_registry_address),
                    abi=_TRANSACTION_REGISTRY_ABI,
                )

            self._enabled = True
            logger.info("Settlement client initialised (chain_id=%d)", chain_id)
        except Exception as exc:
            logger.warning("Settlement client init failed: %s", exc)

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    # ── helpers ───────────────────────────────────────────────

    def _send_tx(self, contract_fn: Any) -> Optional[TxReceipt]:
        if not self._enabled or not self._account:
            return None
        try:
            tx = contract_fn.build_transaction(
                {
                    "from": self._account.address,
                    "nonce": self._w3.eth.get_transaction_count(self._account.address),
                    "gas": 300_000,
                    "gasPrice": self._w3.eth.gas_price,
                    "chainId": self._chain_id,
                }
            )
            signed = self._account.sign_transaction(tx)
            tx_hash = self._w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
            return TxReceipt(
                tx_hash=receipt.transactionHash.hex(),
                block_number=receipt.blockNumber,
                status=receipt.status,
            )
        except Exception as exc:
            logger.error("Settlement tx failed: %s", exc)
            return None

    @staticmethod
    def _to_bytes32(value: str) -> bytes:
        import hashlib
        return hashlib.sha256(value.encode()).digest()

    # ── SettlementAnchor ─────────────────────────────────────

    def anchor_state_root(
        self, state_root: str, l2_block_number: int, proof: bytes = b""
    ) -> Optional[TxReceipt]:
        """Anchor an L2 state root on the settlement layer."""
        if not self._anchor_contract:
            logger.info("SettlementAnchor not configured – skipping anchor")
            return None
        fn = self._anchor_contract.functions.anchorStateRoot(
            self._to_bytes32(state_root),
            l2_block_number,
            proof,
        )
        return self._send_tx(fn)

    def verify_state_root(self, state_root: str) -> Optional[dict]:
        """Check whether a state root has been anchored on L1."""
        if not self._anchor_contract:
            return None
        try:
            result = self._anchor_contract.functions.verifyStateRoot(
                self._to_bytes32(state_root)
            ).call()
            return {
                "exists": result[0],
                "l2_block_number": result[1],
                "anchored_at": result[2],
            }
        except Exception as exc:
            logger.error("Verify state root failed: %s", exc)
            return None

    # ── CanonicalIdentityNFT ─────────────────────────────────

    def mint_identity(
        self, wallet: str, puf_commitment: str, metadata_uri: str = ""
    ) -> Optional[TxReceipt]:
        """Mint a canonical identity NFT (ERC-721) linked to a PUF commitment."""
        if not self._identity_contract:
            logger.info("CanonicalIdentityNFT not configured – skipping mint")
            return None
        fn = self._identity_contract.functions.mintIdentity(
            self._w3.to_checksum_address(wallet),
            self._to_bytes32(puf_commitment),
            metadata_uri,
        )
        return self._send_tx(fn)

    def verify_identity_token(self, token_id: int) -> Optional[dict]:
        """Verify a canonical identity NFT on-chain."""
        if not self._identity_contract:
            return None
        try:
            result = self._identity_contract.functions.verifyIdentity(token_id).call()
            return {
                "owner": result[0],
                "puf_commitment": result[1].hex(),
                "active": result[2],
            }
        except Exception as exc:
            logger.error("Verify identity token failed: %s", exc)
            return None

    # ── TransactionRegistry ──────────────────────────────────

    def register_transaction(
        self, tx_id: str, payload_hash: str, sender: str
    ) -> Optional[TxReceipt]:
        """Register a critical transaction on the settlement layer."""
        if not self._tx_registry_contract:
            logger.info("TransactionRegistry not configured – skipping registration")
            return None
        fn = self._tx_registry_contract.functions.registerTransaction(
            self._to_bytes32(tx_id),
            self._to_bytes32(payload_hash),
            self._w3.to_checksum_address(sender),
        )
        return self._send_tx(fn)
