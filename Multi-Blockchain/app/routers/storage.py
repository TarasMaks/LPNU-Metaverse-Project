"""IPFS hybrid storage endpoints."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import DBStoragePin, get_db
from ..ipfs_storage import IPFSStorage
from ..schemas import (
    StoragePinRequest,
    StoragePinResponse,
    StorageResolveRequest,
    StorageResolveResponse,
)
from ..settlement import SettlementClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/storage", tags=["storage"])

_ipfs: Optional[IPFSStorage] = None
_settlement: Optional[SettlementClient] = None


def set_dependencies(ipfs: IPFSStorage, settlement: SettlementClient) -> None:
    global _ipfs, _settlement
    _ipfs = ipfs
    _settlement = settlement


@router.post("/pin", response_model=StoragePinResponse)
def pin_data(
    request: StoragePinRequest,
    db: Session = Depends(get_db),
) -> StoragePinResponse:
    """Pin data to IPFS and optionally anchor the CID on the settlement layer.

    Large data objects (3D models, tensors, sensor archives) are stored
    off-chain on IPFS; only the Content Identifier (CID) is recorded
    on the blockchain for data integrity verification.
    """
    if _ipfs is None:
        raise HTTPException(status_code=503, detail="IPFS storage not initialised")

    result = _ipfs.pin(request.data, request.filename)

    anchor_tx_hash: Optional[str] = None
    if request.anchor_on_chain and _settlement and _settlement.is_enabled:
        receipt = _settlement.register_transaction(
            tx_id=result["cid"],
            payload_hash=result["cid"],
            sender="system",
        )
        if receipt:
            anchor_tx_hash = receipt.tx_hash

    # Persist pin record
    db_pin = DBStoragePin(
        cid=result["cid"],
        filename=request.filename,
        size_bytes=result["size_bytes"],
        anchor_tx_hash=anchor_tx_hash or "",
    )
    db.add(db_pin)
    db.commit()

    return StoragePinResponse(
        cid=result["cid"],
        size_bytes=result["size_bytes"],
        gateway_url=result["gateway_url"],
        anchor_tx_hash=anchor_tx_hash,
    )


@router.post("/resolve", response_model=StorageResolveResponse)
def resolve_data(
    request: StorageResolveRequest,
) -> StorageResolveResponse:
    """Resolve a CID and retrieve the stored data."""
    if _ipfs is None:
        raise HTTPException(status_code=503, detail="IPFS storage not initialised")

    result = _ipfs.resolve(request.cid)
    if result is None:
        raise HTTPException(status_code=404, detail="CID not found")

    return StorageResolveResponse(
        cid=result["cid"],
        data=result["data"],
        size_bytes=result["size_bytes"],
    )
