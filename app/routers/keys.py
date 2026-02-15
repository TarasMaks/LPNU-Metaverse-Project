"""Key-wrapping endpoint (KMS placeholder with actual encryption)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..audit import record_event
from ..config import Settings, get_settings
from ..crypto import encrypt_template, generate_nonce
from ..database import get_db
from ..schemas import WrapKeyRequest, WrapKeyResponse
from ..security import require_api_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/keys", tags=["Key Management"])


@router.post("/wrap", response_model=WrapKeyResponse)
def wrap_key(
    payload: WrapKeyRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _key: str | None = Depends(require_api_key),
) -> WrapKeyResponse:
    # Generate a per-request data encryption key (DEK)
    dek = generate_nonce(16)

    # Wrap the DEK using the server's master encryption key
    wrapped_blob = encrypt_template(dek.encode(), settings.template_encryption_key)
    wrapped_key = wrapped_blob.to_b64()

    record_event(
        db,
        event_type="keys.wrap",
        outcome="success",
        actor_did=payload.did,
        resource=payload.resource,
        detail=f"level={payload.policy_level}",
    )

    return WrapKeyResponse(wrapped_key=wrapped_key, policy_level=payload.policy_level)
