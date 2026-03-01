"""Pydantic request / response schemas for the Multi-Blockchain REST API."""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────


class TargetLayer(str, Enum):
    """Target blockchain layer for transaction routing."""

    SETTLEMENT = "settlement"
    EXECUTION = "execution"


class TransactionCriticality(str, Enum):
    """Criticality classification for adaptive routing."""

    CRITICAL = "critical"
    STANDARD = "standard"
    LOW = "low"


class TransactionStatus(str, Enum):
    PENDING = "pending"
    ROUTED = "routed"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"


# ── Transaction routing ────────────────────────────────────────


class TransactionSubmitRequest(BaseModel):
    payload: str = Field(..., description="Hex-encoded transaction payload")
    sender: str = Field(..., description="Sender wallet address")
    criticality: TransactionCriticality = Field(
        TransactionCriticality.STANDARD,
        description="Transaction criticality level",
    )
    integrity_requirement: float = Field(
        0.5, ge=0.0, le=1.0,
        description="Required integrity level (0=low, 1=max)",
    )
    data_size_bytes: int = Field(0, ge=0, description="Size of associated data")
    max_latency_ms: int = Field(5000, ge=0, description="Maximum acceptable latency in ms")
    legal_risk: float = Field(
        0.0, ge=0.0, le=1.0,
        description="Probability of legal dispute (0=none, 1=certain)",
    )
    confidentiality: float = Field(
        0.0, ge=0.0, le=1.0,
        description="Confidentiality requirement (0=public, 1=private)",
    )
    metadata: Dict[str, str] = Field(default_factory=dict)


class RoutingDecision(BaseModel):
    target_layer: TargetLayer
    reason: str
    estimated_cost_wei: int = 0
    estimated_latency_ms: int = 0
    confidence: float = Field(1.0, ge=0.0, le=1.0)


class TransactionSubmitResponse(BaseModel):
    tx_id: str
    routing: RoutingDecision
    status: TransactionStatus
    tx_hash: Optional[str] = None


class TransactionStatusResponse(BaseModel):
    tx_id: str
    status: TransactionStatus
    target_layer: TargetLayer
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None
    anchor_tx_hash: Optional[str] = None


# ── Canonical Identity (PUF + NFT) ──────────────────────────


class IdentityRegisterRequest(BaseModel):
    subject_id: str = Field(..., description="Unique subject identifier")
    puf_response: str = Field(..., description="Hex-encoded PUF biometric response")
    wallet_address: str = Field(..., description="Subject wallet address")
    metadata_uri: str = Field("", description="Off-chain metadata URI (IPFS CID)")


class IdentityRegisterResponse(BaseModel):
    token_id: str
    did: str
    puf_commitment: str
    nft_tx_hash: Optional[str] = None


class IdentityVerifyRequest(BaseModel):
    subject_id: str = Field(..., description="Subject identifier to verify")
    puf_response: str = Field(..., description="Current PUF biometric response")


class IdentityVerifyResponse(BaseModel):
    verified: bool
    did: str
    token_id: str
    confidence: float = Field(1.0, ge=0.0, le=1.0)


# ── IPFS / Hybrid Storage ───────────────────────────────────


class StoragePinRequest(BaseModel):
    data: str = Field(..., description="Base-64 encoded data to store off-chain")
    filename: str = Field("", description="Optional filename hint")
    anchor_on_chain: bool = Field(
        True,
        description="Whether to anchor the CID on the settlement layer",
    )


class StoragePinResponse(BaseModel):
    cid: str
    size_bytes: int
    gateway_url: str
    anchor_tx_hash: Optional[str] = None


class StorageResolveRequest(BaseModel):
    cid: str = Field(..., description="IPFS Content Identifier")


class StorageResolveResponse(BaseModel):
    cid: str
    data: str = Field(..., description="Base-64 encoded data")
    size_bytes: int


# ── L2 → L1 State Anchoring ─────────────────────────────────


class AnchorSubmitRequest(BaseModel):
    state_root: str = Field(..., description="Hex-encoded L2 state root hash")
    block_number: int = Field(..., description="L2 block number")
    proof: str = Field("", description="Optional validity / fraud proof")


class AnchorSubmitResponse(BaseModel):
    anchor_id: str
    l1_tx_hash: Optional[str] = None
    state_root: str
    l2_block_number: int


class AnchorVerifyRequest(BaseModel):
    state_root: str = Field(..., description="State root to verify on L1")


class AnchorVerifyResponse(BaseModel):
    verified: bool
    anchor_id: Optional[str] = None
    l1_block_number: Optional[int] = None
    anchored_at: Optional[int] = None


# ── Webhook events ──────────────────────────────────────────


class WebhookEvent(BaseModel):
    event_type: str
    chain_id: int
    tx_hash: str
    block_number: int
    data: Dict[str, str] = Field(default_factory=dict)


# ── Health ──────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str
    settlement_layer: bool
    execution_layer: bool
    ipfs: bool
    middleware_nodes: int
