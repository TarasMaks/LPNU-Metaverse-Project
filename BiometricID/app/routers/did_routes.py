"""DID generation and identity management endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..audit import record_event
from ..blockchain import BlockchainClient
from ..database import DBIdentity, get_db
from ..did import generate_did
from ..schemas import DIDCreateRequest, DIDCreateResponse
from ..security import require_api_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/did", tags=["DID"])

_blockchain: BlockchainClient | None = None


def set_blockchain_client(bc: BlockchainClient) -> None:
    global _blockchain
    _blockchain = bc


@router.post("", response_model=DIDCreateResponse)
def create_did(
    payload: DIDCreateRequest,
    db: Session = Depends(get_db),
    _key: str | None = Depends(require_api_key),
) -> DIDCreateResponse:
    doc = generate_did(method=payload.method, wallet_address=payload.wallet_address)

    # Persist identity
    identity = DBIdentity(
        did=doc.did,
        wallet_address=doc.wallet_address,
        public_key_pem=doc.public_key_pem,
    )
    db.add(identity)
    db.commit()

    # Register on blockchain (best-effort)
    if _blockchain and _blockchain.is_enabled and doc.wallet_address.startswith("0x"):
        _blockchain.register_identity(doc.did, doc.wallet_address)

    record_event(db, event_type="did.created", outcome="success", actor_did=doc.did)

    return DIDCreateResponse(
        did=doc.did,
        wallet_address=doc.wallet_address,
        public_key_pem=doc.public_key_pem,
    )
