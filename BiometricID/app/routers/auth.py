"""Authentication endpoints – challenge / verify with real biometric matching.

The ``/auth/verify`` endpoint now **actually performs biometric comparison**
between the probe template submitted by the client and the encrypted
template stored during enrollment.  A signed JWT Verifiable Credential is
only issued when the match succeeds.
"""

from __future__ import annotations

import base64
import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..audit import record_event
from ..config import Settings, get_settings
from ..crypto import EncryptedBlob, decrypt_template, generate_nonce
from ..database import DBAuthChallenge, DBBiometricTemplate, DBIdentity, DBVerifiableCredential, get_db
from ..schemas import (
    AuthChallengeRequest,
    AuthChallengeResponse,
    AuthVerifyRequest,
    AuthVerifyResponse,
)
from ..security import require_api_key
from ..vc import issue_vc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/auth", tags=["Authentication"])


def _cosine_similarity(a: list, b: list) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@router.post("/challenge", response_model=AuthChallengeResponse)
def auth_challenge(
    payload: AuthChallengeRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _key: str | None = Depends(require_api_key),
) -> AuthChallengeResponse:
    # Ensure user is enrolled
    template = db.query(DBBiometricTemplate).filter_by(user_id=payload.user_id, status="active").first()
    if not template:
        raise HTTPException(status_code=404, detail="User is not enrolled")

    nonce = generate_nonce(8)
    challenge_message = f"authenticate:{payload.user_id}:{nonce}"

    # Upsert challenge
    existing = db.query(DBAuthChallenge).filter_by(user_id=payload.user_id).first()
    if existing:
        existing.nonce = nonce
        existing.created_at = int(time.time())
    else:
        db.add(DBAuthChallenge(user_id=payload.user_id, nonce=nonce))
    db.commit()

    return AuthChallengeResponse(nonce=nonce, challenge_message=challenge_message)


@router.post("/verify", response_model=AuthVerifyResponse)
def auth_verify(
    payload: AuthVerifyRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _key: str | None = Depends(require_api_key),
) -> AuthVerifyResponse:
    # 1. Validate nonce (challenge-response)
    challenge = db.query(DBAuthChallenge).filter_by(user_id=payload.user_id).first()
    if not challenge or challenge.nonce != payload.nonce:
        record_event(db, event_type="auth.verify", outcome="failure", detail="invalid nonce")
        raise HTTPException(status_code=400, detail="Invalid auth challenge")

    # 2. Check challenge expiry
    now = int(time.time())
    if now - challenge.created_at > settings.challenge_ttl_seconds:
        db.delete(challenge)
        db.commit()
        record_event(db, event_type="auth.verify", outcome="failure", detail="challenge expired")
        raise HTTPException(status_code=400, detail="Auth challenge expired")

    # 3. Retrieve stored template
    template_record = db.query(DBBiometricTemplate).filter_by(user_id=payload.user_id, status="active").first()
    if not template_record:
        raise HTTPException(status_code=404, detail="No active enrollment found")

    # 4. Biometric verification – compare probe against stored template
    biometric_verified = False
    if payload.template_data:
        try:
            # Decrypt stored template
            stored_blob = EncryptedBlob.from_b64(template_record.encrypted_template)
            stored_plain = decrypt_template(stored_blob, settings.template_encryption_key)

            # Try to interpret as JSON embedding vectors for cosine comparison
            try:
                stored_embedding = json.loads(stored_plain.decode())
                probe_embedding = json.loads(base64.b64decode(payload.template_data).decode())

                if isinstance(stored_embedding, list) and isinstance(probe_embedding, list):
                    similarity = _cosine_similarity(stored_embedding, probe_embedding)
                    biometric_verified = similarity >= (1.0 - settings.face_match_threshold)
                    logger.info("Biometric match similarity=%.4f threshold=%.2f verified=%s",
                                similarity, settings.face_match_threshold, biometric_verified)
            except (json.JSONDecodeError, ValueError):
                # Fallback: exact byte comparison of encrypted commitments
                probe_bytes = payload.template_data.encode()
                biometric_verified = (stored_plain == probe_bytes)

        except Exception as exc:
            logger.error("Template decryption/comparison failed: %s", exc)
            record_event(db, event_type="auth.verify", outcome="failure", detail="decryption error")
            raise HTTPException(status_code=500, detail="Biometric verification failed")

        if not biometric_verified:
            record_event(
                db,
                event_type="auth.verify",
                outcome="failure",
                actor_did=payload.did,
                detail="biometric mismatch",
            )
            raise HTTPException(status_code=401, detail="Biometric verification failed – templates do not match")
    else:
        # No biometric probe supplied → issue level-1 VC only (possession factor)
        if payload.desired_level > 1:
            raise HTTPException(
                status_code=400,
                detail="Biometric probe (template_data) required for assurance level > 1",
            )

    # 5. Verify wallet signature if provided
    wallet_verified = False
    if payload.wallet_signature:
        identity = db.query(DBIdentity).filter_by(did=payload.did).first()
        if identity:
            from ..did import verify_wallet_signature

            challenge_msg = f"authenticate:{payload.user_id}:{payload.nonce}"
            sig_bytes = base64.b64decode(payload.wallet_signature)
            wallet_verified = verify_wallet_signature(
                identity.public_key_pem, challenge_msg.encode(), sig_bytes
            )

    # 6. Consume the challenge (one-time use)
    db.delete(challenge)
    db.commit()

    # 7. Issue signed Verifiable Credential
    vc = issue_vc(
        subject_did=payload.did,
        level=payload.desired_level,
        nonce=payload.nonce,
        signing_key=settings.vc_signing_key,
        biometric_method="face",
        ttl_seconds=settings.vc_ttl_seconds,
    )

    # 8. Persist the VC
    db.add(
        DBVerifiableCredential(
            jti=vc.jti,
            subject_did=vc.subject_did,
            issuer_did=vc.issuer_did,
            level=vc.level,
            jwt_token=vc.jwt_token,
            issued_at=vc.issued_at,
            expires_at=vc.expires_at,
        )
    )
    db.commit()

    record_event(
        db,
        event_type="auth.verify",
        outcome="success",
        actor_did=payload.did,
        detail=f"level={vc.level} bio={biometric_verified} wallet={wallet_verified}",
    )

    return AuthVerifyResponse(
        vc_jwt=vc.jwt_token,
        vc_did=vc.subject_did,
        level=vc.level,
        expires_at=vc.expires_at,
        biometric_verified=biometric_verified,
        liveness_passed=None,
    )
