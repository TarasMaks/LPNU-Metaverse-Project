from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


def sha256_hex(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generate_nonce(length: int = 16) -> str:
    return secrets.token_hex(length)


def now_ts() -> int:
    return int(time.time())


@dataclass
class EnrollmentChallenge:
    challenge: str
    user_id: str
    created_at: int = field(default_factory=now_ts)


@dataclass
class AuthChallenge:
    nonce: str
    user_id: str
    created_at: int = field(default_factory=now_ts)


@dataclass
class BiometricTemplateRecord:
    user_id: str
    commitment: str
    storage_uri: str
    version: str
    status: str = "active"


@dataclass
class VerifiableCredential:
    subject_did: str
    level: int
    expires_at: int
    nonce: str

    def is_valid(self) -> bool:
        return now_ts() < self.expires_at


@dataclass
class Policy:
    level: int
    required_factors: Set[str]
    description: str


@dataclass
class AccessDecision:
    granted: bool
    reasons: List[str]
    level_required: int
    level_provided: int


class InMemoryStore:
    """Simple in-memory store to keep PoC state."""

    def __init__(self) -> None:
        self.enrollment_challenges: Dict[str, EnrollmentChallenge] = {}
        self.auth_challenges: Dict[str, AuthChallenge] = {}
        self.templates: Dict[str, BiometricTemplateRecord] = {}
        self.credentials: Dict[str, VerifiableCredential] = {}

    def add_enrollment_challenge(self, challenge: EnrollmentChallenge) -> None:
        self.enrollment_challenges[challenge.user_id] = challenge

    def add_auth_challenge(self, challenge: AuthChallenge) -> None:
        self.auth_challenges[challenge.user_id] = challenge

    def record_template(self, record: BiometricTemplateRecord) -> None:
        self.templates[record.user_id] = record

    def store_credential(self, vc: VerifiableCredential) -> None:
        self.credentials[vc.subject_did] = vc


def compute_commitment(template_data: str, salt: str, version: str) -> str:
    return sha256_hex(f"{template_data}||{salt}||{version}")


def issue_vc(did: str, level: int, nonce: str, ttl_seconds: int = 600) -> VerifiableCredential:
    return VerifiableCredential(
        subject_did=did,
        level=level,
        expires_at=now_ts() + ttl_seconds,
        nonce=nonce,
    )
