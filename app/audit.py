"""Structured audit logging – records security-relevant events to the database
and to the Python logging subsystem.

Events are recorded without any PII or raw biometric data, in line with GDPR
requirements specified in the design document.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from sqlalchemy.orm import Session

from .database import DBAuditEvent

logger = logging.getLogger("audit")


def record_event(
    db: Session,
    *,
    event_type: str,
    outcome: str,
    actor_did: str = "",
    resource: str = "",
    detail: str = "",
    ip_address: str = "",
) -> DBAuditEvent:
    """Persist an audit event and emit a structured log line."""
    evt = DBAuditEvent(
        event_type=event_type,
        actor_did=actor_did,
        resource=resource,
        outcome=outcome,
        detail=detail,
        ip_address=ip_address,
        timestamp=int(time.time()),
    )
    db.add(evt)
    db.commit()
    db.refresh(evt)

    logger.info(
        "audit event_type=%s outcome=%s actor=%s resource=%s detail=%s ip=%s",
        event_type,
        outcome,
        actor_did,
        resource,
        detail,
        ip_address,
    )
    return evt
