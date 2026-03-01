"""W3C-style Verifiable Credentials implemented as signed JWTs.

Each VC contains:
- ``iss``  – issuer DID
- ``sub``  – subject DID
- ``jti``  – unique credential ID
- ``iat``  – issuance timestamp
- ``exp``  – expiration timestamp
- ``vc``   – credential payload (assurance level, biometric method, nonce)

The JWT is signed with HS256 using the server's ``vc_signing_key``.
In production this should use an asymmetric algorithm (ES256 / EdDSA)
bound to the issuer's DID key.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

import jwt


ISSUER_DID = "did:key:biometric-identity-service"


@dataclass
class VerifiableCredential:
    jti: str
    subject_did: str
    issuer_did: str
    level: int
    biometric_method: str
    nonce: str
    issued_at: int
    expires_at: int
    jwt_token: str

    def is_valid(self) -> bool:
        return int(time.time()) < self.expires_at


def issue_vc(
    subject_did: str,
    level: int,
    nonce: str,
    signing_key: str,
    biometric_method: str = "face",
    ttl_seconds: int = 600,
    issuer_did: str = ISSUER_DID,
) -> VerifiableCredential:
    """Issue a signed JWT Verifiable Credential."""
    now = int(time.time())
    jti = str(uuid.uuid4())

    payload: Dict[str, Any] = {
        "iss": issuer_did,
        "sub": subject_did,
        "jti": jti,
        "iat": now,
        "exp": now + ttl_seconds,
        "vc": {
            "type": ["VerifiableCredential", "BiometricAssurance"],
            "credentialSubject": {
                "assuranceLevel": level,
                "biometricMethod": biometric_method,
                "nonce": nonce,
            },
        },
    }

    token = jwt.encode(payload, signing_key, algorithm="HS256")

    return VerifiableCredential(
        jti=jti,
        subject_did=subject_did,
        issuer_did=issuer_did,
        level=level,
        biometric_method=biometric_method,
        nonce=nonce,
        issued_at=now,
        expires_at=now + ttl_seconds,
        jwt_token=token,
    )


def verify_vc_token(token: str, signing_key: str) -> Optional[Dict[str, Any]]:
    """Decode and verify a VC JWT.  Returns the payload dict or *None* on failure."""
    try:
        return jwt.decode(token, signing_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
