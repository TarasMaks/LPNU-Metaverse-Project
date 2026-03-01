"""Canonical identity (PUF + NFT) endpoints."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import DBCanonicalIdentity, get_db
from ..identity import CanonicalIdentityManager
from ..schemas import (
    IdentityRegisterRequest,
    IdentityRegisterResponse,
    IdentityVerifyRequest,
    IdentityVerifyResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/identity", tags=["identity"])

_identity_mgr: Optional[CanonicalIdentityManager] = None


def set_identity_manager(mgr: CanonicalIdentityManager) -> None:
    global _identity_mgr
    _identity_mgr = mgr


@router.post("/register", response_model=IdentityRegisterResponse)
def register_identity(
    request: IdentityRegisterRequest,
    db: Session = Depends(get_db),
) -> IdentityRegisterResponse:
    """Register a new canonical identity using PUF biometric response.

    Creates a deterministic DID from the PUF commitment and mints an
    NFT token on the settlement layer (when available).
    """
    if _identity_mgr is None:
        raise HTTPException(status_code=503, detail="Identity manager not initialised")

    # Check for duplicates
    existing = (
        db.query(DBCanonicalIdentity)
        .filter(DBCanonicalIdentity.subject_id == request.subject_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Subject already registered")

    result = _identity_mgr.register(
        subject_id=request.subject_id,
        puf_response=request.puf_response,
        wallet_address=request.wallet_address,
        metadata_uri=request.metadata_uri,
    )

    # Persist to database
    db_identity = DBCanonicalIdentity(
        subject_id=request.subject_id,
        did=result["did"],
        wallet_address=request.wallet_address,
        puf_commitment=result["puf_commitment"],
        token_id=result["token_id"],
        metadata_uri=request.metadata_uri,
        nft_tx_hash=result["nft_tx_hash"] or "",
    )
    db.add(db_identity)
    db.commit()

    return IdentityRegisterResponse(
        token_id=result["token_id"],
        did=result["did"],
        puf_commitment=result["puf_commitment"],
        nft_tx_hash=result["nft_tx_hash"],
    )


@router.post("/verify", response_model=IdentityVerifyResponse)
def verify_identity(
    request: IdentityVerifyRequest,
    db: Session = Depends(get_db),
) -> IdentityVerifyResponse:
    """Verify a subject's PUF response against their registered identity."""
    if _identity_mgr is None:
        raise HTTPException(status_code=503, detail="Identity manager not initialised")

    db_identity = (
        db.query(DBCanonicalIdentity)
        .filter(DBCanonicalIdentity.subject_id == request.subject_id)
        .first()
    )
    if not db_identity:
        raise HTTPException(status_code=404, detail="Subject not found")

    result = _identity_mgr.verify(
        subject_id=request.subject_id,
        puf_response=request.puf_response,
        stored_commitment=db_identity.puf_commitment,
    )

    return IdentityVerifyResponse(
        verified=result["verified"],
        did=result["did"],
        token_id=result["token_id"],
        confidence=result["confidence"],
    )
