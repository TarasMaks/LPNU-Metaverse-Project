"""Biometric enrollment endpoints.

Implements the two-phase enrollment flow:
1. ``/enroll/start`` – issue challenge + salt
2. ``/enroll/finish`` – validate challenge, compute commitment, store
   encrypted template, and optionally record on blockchain.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..audit import record_event
from ..blockchain import BlockchainClient
from ..config import Settings, get_settings
from ..crypto import compute_commitment, encrypt_template, generate_nonce
from ..database import DBBiometricTemplate, DBEnrollmentChallenge, get_db
from ..schemas import (
    EnrollmentFinishRequest,
    EnrollmentFinishResponse,
    EnrollmentStartRequest,
    EnrollmentStartResponse,
)
from ..security import require_api_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/enroll", tags=["Enrollment"])

_blockchain: BlockchainClient | None = None


def set_blockchain_client(bc: BlockchainClient) -> None:
    global _blockchain
    _blockchain = bc


@router.post("/start", response_model=EnrollmentStartResponse)
def enroll_start(
    payload: EnrollmentStartRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _key: str | None = Depends(require_api_key),
) -> EnrollmentStartResponse:
    challenge = generate_nonce(8)
    salt = generate_nonce(4)

    # Upsert enrollment challenge (replace if exists)
    existing = db.query(DBEnrollmentChallenge).filter_by(user_id=payload.user_id).first()
    if existing:
        existing.challenge = challenge
        existing.salt = salt
        existing.version = payload.version
        existing.created_at = int(time.time())
    else:
        db.add(
            DBEnrollmentChallenge(
                user_id=payload.user_id,
                challenge=challenge,
                salt=salt,
                version=payload.version,
            )
        )
    db.commit()

    record_event(db, event_type="enroll.start", outcome="success", detail=f"user={payload.user_id}")

    return EnrollmentStartResponse(challenge=challenge, salt=salt, version=payload.version)


@router.post("/finish", response_model=EnrollmentFinishResponse)
def enroll_finish(
    payload: EnrollmentFinishRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _key: str | None = Depends(require_api_key),
) -> EnrollmentFinishResponse:
    # 1. Validate challenge
    record = db.query(DBEnrollmentChallenge).filter_by(user_id=payload.user_id).first()
    if not record or record.challenge != payload.challenge:
        raise HTTPException(status_code=400, detail="Invalid or missing enrollment challenge")

    # 2. Check challenge expiry
    now = int(time.time())
    if now - record.created_at > settings.challenge_ttl_seconds:
        db.delete(record)
        db.commit()
        raise HTTPException(status_code=400, detail="Enrollment challenge expired")

    # 3. Encrypt the template
    encrypted = encrypt_template(payload.template_data.encode(), settings.template_encryption_key)
    encrypted_b64 = encrypted.to_b64()

    # 4. Compute commitment over encrypted data
    commitment = compute_commitment(encrypted_b64, payload.salt, payload.version)

    # 5. Persist template record
    existing_tmpl = db.query(DBBiometricTemplate).filter_by(user_id=payload.user_id).first()
    if existing_tmpl:
        existing_tmpl.commitment = commitment
        existing_tmpl.encrypted_template = encrypted_b64
        existing_tmpl.storage_uri = payload.storage_uri
        existing_tmpl.version = payload.version
        existing_tmpl.status = "active"
        existing_tmpl.created_at = now
    else:
        db.add(
            DBBiometricTemplate(
                user_id=payload.user_id,
                commitment=commitment,
                encrypted_template=encrypted_b64,
                storage_uri=payload.storage_uri,
                version=payload.version,
            )
        )

    # 6. Consume the challenge (one-time use)
    db.delete(record)
    db.commit()

    # 7. Record on blockchain (best-effort)
    tx_hash = None
    if _blockchain and _blockchain.is_enabled:
        receipt = _blockchain.store_commitment(
            payload.user_id, commitment, payload.version, payload.storage_uri
        )
        if receipt:
            tx_hash = receipt.tx_hash

    record_event(
        db,
        event_type="enroll.finish",
        outcome="success",
        detail=f"user={payload.user_id} commitment={commitment[:16]}…",
    )

    return EnrollmentFinishResponse(
        commitment=commitment,
        storage_uri=payload.storage_uri,
        version=payload.version,
        blockchain_tx=tx_hash,
    )
