"""Domain helpers re-exported for backward compatibility.

The original monolithic models.py has been split into dedicated modules:
- ``app.crypto``   – nonce generation, commitments, encryption
- ``app.database`` – SQLAlchemy ORM models
- ``app.vc``       – Verifiable Credential issuance / verification
- ``app.policy``   – Policy, AccessDecision

This file re-exports the most commonly used symbols so existing imports
continue to work.
"""

from __future__ import annotations

from .crypto import compute_commitment, generate_nonce, sha256_hex
from .database import (
    DBAuthChallenge,
    DBBiometricTemplate,
    DBEnrollmentChallenge,
    DBVerifiableCredential,
)
from .policy import AccessDecision, Policy
from .vc import VerifiableCredential, issue_vc

__all__ = [
    "sha256_hex",
    "generate_nonce",
    "compute_commitment",
    "AccessDecision",
    "Policy",
    "VerifiableCredential",
    "issue_vc",
    "DBEnrollmentChallenge",
    "DBAuthChallenge",
    "DBBiometricTemplate",
    "DBVerifiableCredential",
]
