"""Webhook receiver for event-driven blockchain state synchronisation.

Receives notifications from chain monitoring services (e.g. Alchemy
Notify) and dispatches them through the middleware stack's event handler.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..database import DBWebhookEvent, get_db
from ..middleware_stack import WebhookHandler
from ..schemas import WebhookEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/webhook", tags=["webhooks"])

_webhook_handler: Optional[WebhookHandler] = None


def set_webhook_handler(handler: WebhookHandler) -> None:
    global _webhook_handler
    _webhook_handler = handler


@router.post("/notify")
def receive_webhook(
    event: WebhookEvent,
    db: Session = Depends(get_db),
    x_alchemy_token: str = Header("", alias="X-Alchemy-Token"),
) -> dict:
    """Receive a webhook notification from a chain monitoring service.

    Validates the authentication token, persists the event, and
    dispatches it to registered handlers for real-time UI updates.
    """
    if _webhook_handler is None:
        raise HTTPException(status_code=503, detail="Webhook handler not initialised")

    if not _webhook_handler.validate_token(x_alchemy_token):
        raise HTTPException(status_code=403, detail="Invalid webhook token")

    # Persist event
    db_event = DBWebhookEvent(
        event_type=event.event_type,
        chain_id=event.chain_id,
        tx_hash=event.tx_hash,
        block_number=event.block_number,
        data=json.dumps(event.data),
    )
    db.add(db_event)
    db.commit()

    # Dispatch to handlers
    result = _webhook_handler.process_event(event.model_dump())

    return {"status": "accepted", "event_id": db_event.id, "processing": result}
