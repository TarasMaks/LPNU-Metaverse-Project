"""Transaction submission and routing endpoints."""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import DBTransaction, get_db
from ..execution import ExecutionClient
from ..router_engine import RouterEngine
from ..schemas import (
    TargetLayer,
    TransactionStatus,
    TransactionStatusResponse,
    TransactionSubmitRequest,
    TransactionSubmitResponse,
)
from ..settlement import SettlementClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/transaction", tags=["transactions"])

_router_engine: Optional[RouterEngine] = None
_settlement: Optional[SettlementClient] = None
_execution: Optional[ExecutionClient] = None


def set_dependencies(
    engine: RouterEngine,
    settlement: SettlementClient,
    execution: ExecutionClient,
) -> None:
    global _router_engine, _settlement, _execution
    _router_engine = engine
    _settlement = settlement
    _execution = execution


@router.post("/submit", response_model=TransactionSubmitResponse)
def submit_transaction(
    request: TransactionSubmitRequest,
    db: Session = Depends(get_db),
) -> TransactionSubmitResponse:
    """Submit a transaction for adaptive routing.

    The routing engine evaluates the transaction parameters and selects
    the optimal layer (settlement vs. execution) for processing.
    """
    if _router_engine is None:
        raise HTTPException(status_code=503, detail="Router engine not initialised")

    # Route the transaction
    decision = _router_engine.evaluate(request)

    # Generate transaction ID
    tx_id = uuid.uuid4().hex[:16]
    payload_hash = hashlib.sha256(request.payload.encode()).hexdigest()

    # Submit to the target layer
    tx_hash: Optional[str] = None
    status = TransactionStatus.ROUTED

    if decision.target_layer == TargetLayer.SETTLEMENT and _settlement and _settlement.is_enabled:
        receipt = _settlement.register_transaction(
            tx_id=tx_id,
            payload_hash=payload_hash,
            sender=request.sender,
        )
        if receipt:
            tx_hash = receipt.tx_hash
            status = TransactionStatus.CONFIRMED
    elif decision.target_layer == TargetLayer.EXECUTION and _execution and _execution.is_enabled:
        receipt = _execution.submit_data(
            payload_hash=payload_hash,
            sender=request.sender,
            category=request.criticality.value,
        )
        if receipt:
            tx_hash = receipt.tx_hash
            status = TransactionStatus.CONFIRMED

    # Persist to database
    db_tx = DBTransaction(
        tx_id=tx_id,
        sender=request.sender,
        payload_hash=payload_hash,
        target_layer=decision.target_layer.value,
        criticality=request.criticality.value,
        status=status.value,
        tx_hash=tx_hash or "",
        routing_reason=decision.reason,
    )
    db.add(db_tx)
    db.commit()

    return TransactionSubmitResponse(
        tx_id=tx_id,
        routing=decision,
        status=status,
        tx_hash=tx_hash,
    )


@router.get("/status/{tx_id}", response_model=TransactionStatusResponse)
def get_transaction_status(
    tx_id: str,
    db: Session = Depends(get_db),
) -> TransactionStatusResponse:
    """Check the status of a previously submitted transaction."""
    db_tx = db.query(DBTransaction).filter(DBTransaction.tx_id == tx_id).first()
    if not db_tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return TransactionStatusResponse(
        tx_id=db_tx.tx_id,
        status=TransactionStatus(db_tx.status),
        target_layer=TargetLayer(db_tx.target_layer),
        tx_hash=db_tx.tx_hash or None,
        block_number=db_tx.block_number,
        anchor_tx_hash=db_tx.anchor_tx_hash or None,
    )
