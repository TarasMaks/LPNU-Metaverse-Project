"""Access-control endpoint with server-side factor verification."""

from __future__ import annotations

import base64
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..audit import record_event
from ..config import Settings, get_settings
from ..database import DBIdentity, DBVerifiableCredential, get_db
from ..policy import (
    AccessDecision,
    assess_risk,
    evaluate_access,
    step_up_if_risky,
    verify_factors,
)
from ..schemas import AccessRequest, AccessResponse
from ..security import require_api_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/access", tags=["Access Control"])


@router.post("/request", response_model=AccessResponse)
def access_request(
    payload: AccessRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _key: str | None = Depends(require_api_key),
) -> AccessResponse:
    # 1. Validate the VC exists and is not expired / revoked
    vc_record = (
        db.query(DBVerifiableCredential)
        .filter_by(subject_did=payload.did, revoked=0)
        .order_by(DBVerifiableCredential.expires_at.desc())
        .first()
    )
    if not vc_record or vc_record.expires_at < int(time.time()):
        record_event(
            db,
            event_type="access.request",
            outcome="denied",
            actor_did=payload.did,
            resource=payload.resource,
            detail="missing or expired VC",
        )
        raise HTTPException(status_code=403, detail="Missing or expired VC")

    # 2. Server-side risk assessment
    client_ip = request.client.host if request.client else ""
    server_risk = assess_risk(current_ip=client_ip)
    # Merge with any known-good client indicators, but do NOT trust raw client list
    all_risk = server_risk  # client risk_indicators are informational, not authoritative

    # 3. Step up the required level
    adjusted_level = step_up_if_risky(payload.desired_level, all_risk)
    if vc_record.level < adjusted_level:
        record_event(
            db,
            event_type="access.request",
            outcome="denied",
            actor_did=payload.did,
            resource=payload.resource,
            detail=f"VC level {vc_record.level} < required {adjusted_level}",
        )
        raise HTTPException(
            status_code=403,
            detail=f"VC level {vc_record.level} insufficient (need {adjusted_level} after risk adjustment)",
        )

    # 4. Server-side factor verification
    identity = db.query(DBIdentity).filter_by(did=payload.did).first()
    wallet_pubkey = identity.public_key_pem if identity else None
    challenge_msg = f"access:{payload.did}:{payload.resource}".encode()

    wallet_sig = base64.b64decode(payload.wallet_signature) if payload.wallet_signature else None

    proofs = verify_factors(
        payload.factors,
        wallet_signature=wallet_sig,
        wallet_pubkey_pem=wallet_pubkey,
        challenge_message=challenge_msg,
        vc_jwt=payload.vc_jwt or vc_record.jwt_token,
        vc_signing_key=settings.vc_signing_key,
        device_attestation_token=payload.device_attestation_token or None,
        oob_code=payload.oob_code or None,
        expected_oob_code=None,  # would come from a server-side OOB store
    )
    verified_names = {p.factor for p in proofs if p.verified}

    # 5. Evaluate policy with verified factors only
    decision: AccessDecision = evaluate_access(
        resource=payload.resource,
        desired_level=adjusted_level,
        presented_factors=payload.factors,
        verified_factor_names=verified_names,
    )

    record_event(
        db,
        event_type="access.request",
        outcome="granted" if decision.granted else "denied",
        actor_did=payload.did,
        resource=payload.resource,
        detail="; ".join(decision.reasons),
        ip_address=client_ip,
    )

    return AccessResponse(
        granted=decision.granted,
        reasons=decision.reasons,
        level_required=decision.level_required,
        level_provided=decision.level_provided,
        factor_proofs=[{"factor": p.factor, "verified": str(p.verified), "detail": p.detail} for p in proofs],
    )
