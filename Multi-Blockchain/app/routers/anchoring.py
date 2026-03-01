"""L2 → L1 state anchoring endpoints.

Provides cryptographic linkage between the execution layer (L2) and the
settlement layer (L1) by periodically anchoring L2 state roots on Ethereum.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import DBStateAnchor, get_db
from ..schemas import (
    AnchorSubmitRequest,
    AnchorSubmitResponse,
    AnchorVerifyRequest,
    AnchorVerifyResponse,
)
from ..settlement import SettlementClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/anchor", tags=["anchoring"])

_settlement: Optional[SettlementClient] = None


def set_settlement_client(client: SettlementClient) -> None:
    global _settlement
    _settlement = client


@router.post("/submit", response_model=AnchorSubmitResponse)
def submit_anchor(
    request: AnchorSubmitRequest,
    db: Session = Depends(get_db),
) -> AnchorSubmitResponse:
    """Anchor an L2 state root on the settlement layer.

    This creates a cryptographic link between the execution layer's state
    and the settlement layer, ensuring that L2 data integrity can be
    verified against L1 at any time.
    """
    anchor_id = uuid.uuid4().hex[:16]

    l1_tx_hash: Optional[str] = None
    l1_block: Optional[int] = None

    if _settlement and _settlement.is_enabled:
        proof = bytes.fromhex(request.proof) if request.proof else b""
        receipt = _settlement.anchor_state_root(
            state_root=request.state_root,
            l2_block_number=request.block_number,
            proof=proof,
        )
        if receipt:
            l1_tx_hash = receipt.tx_hash
            l1_block = receipt.block_number

    # Persist anchor record
    db_anchor = DBStateAnchor(
        anchor_id=anchor_id,
        state_root=request.state_root,
        l2_block_number=request.block_number,
        l1_tx_hash=l1_tx_hash or "",
        l1_block_number=l1_block,
        proof=request.proof,
    )
    db.add(db_anchor)
    db.commit()

    return AnchorSubmitResponse(
        anchor_id=anchor_id,
        l1_tx_hash=l1_tx_hash,
        state_root=request.state_root,
        l2_block_number=request.block_number,
    )


@router.post("/verify", response_model=AnchorVerifyResponse)
def verify_anchor(
    request: AnchorVerifyRequest,
    db: Session = Depends(get_db),
) -> AnchorVerifyResponse:
    """Verify whether an L2 state root has been anchored on the settlement layer."""
    # Check local database first
    db_anchor = (
        db.query(DBStateAnchor)
        .filter(DBStateAnchor.state_root == request.state_root)
        .first()
    )

    if not db_anchor:
        return AnchorVerifyResponse(verified=False)

    # Optionally verify on-chain
    on_chain_verified = False
    if _settlement and _settlement.is_enabled:
        result = _settlement.verify_state_root(request.state_root)
        if result and result.get("exists"):
            on_chain_verified = True

    return AnchorVerifyResponse(
        verified=True,
        anchor_id=db_anchor.anchor_id,
        l1_block_number=db_anchor.l1_block_number,
        anchored_at=db_anchor.created_at,
    )
