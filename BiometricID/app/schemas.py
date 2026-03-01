"""Pydantic request / response schemas for the REST API.

Extracted from the monolithic main.py to keep endpoint handlers lean.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ── DID ──────────────────────────────────────────────────────


class DIDCreateRequest(BaseModel):
    method: str = Field("key", description="DID method (e.g. 'key')")
    wallet_address: str = Field("", description="Optional pre-existing wallet address to bind")


class DIDCreateResponse(BaseModel):
    did: str
    wallet_address: str
    public_key_pem: str


# ── Enrollment ───────────────────────────────────────────────


class EnrollmentStartRequest(BaseModel):
    user_id: str = Field(..., description="Application user identifier")
    version: str = Field("v1", description="Template version / algorithm hint")


class EnrollmentStartResponse(BaseModel):
    challenge: str
    salt: str
    version: str


class EnrollmentFinishRequest(BaseModel):
    user_id: str
    template_data: str = Field(..., description="Base-64 encoded biometric template or raw embedding")
    salt: str
    version: str
    storage_uri: str = Field("", description="Off-chain encrypted storage URI (e.g. ipfs://…)")
    challenge: str


class EnrollmentFinishResponse(BaseModel):
    commitment: str
    storage_uri: str
    version: str
    blockchain_tx: Optional[str] = None


# ── Authentication ───────────────────────────────────────────


class AuthChallengeRequest(BaseModel):
    user_id: str


class AuthChallengeResponse(BaseModel):
    nonce: str
    challenge_message: str = Field("", description="Message to sign with wallet key")


class AuthVerifyRequest(BaseModel):
    user_id: str
    did: str
    nonce: str
    desired_level: int = Field(2, description="Requested assurance level for the VC")
    template_data: str = Field("", description="Biometric probe (base-64 embedding) for server-side match")
    wallet_signature: str = Field("", description="Base-64 ECDSA signature of the challenge message")


class AuthVerifyResponse(BaseModel):
    vc_jwt: str
    vc_did: str
    level: int
    expires_at: int
    biometric_verified: bool
    liveness_passed: Optional[bool] = None


# ── Access ───────────────────────────────────────────────────


class AccessRequest(BaseModel):
    did: str
    resource: str
    desired_level: int
    factors: List[str]
    vc_jwt: str = Field("", description="Biometric VC JWT token for server-side factor validation")
    wallet_signature: str = Field("", description="Base-64 wallet signature of the access challenge")
    device_attestation_token: str = Field("", description="Device attestation token")
    oob_code: str = Field("", description="Out-of-band confirmation code")
    risk_indicators: Optional[List[str]] = Field(default_factory=list)


class AccessResponse(BaseModel):
    granted: bool
    reasons: List[str]
    level_required: int
    level_provided: int
    factor_proofs: Optional[List[Dict[str, str]]] = None


# ── Key wrapping ─────────────────────────────────────────────


class WrapKeyRequest(BaseModel):
    resource: str
    did: str
    policy_level: int


class WrapKeyResponse(BaseModel):
    wrapped_key: str
    policy_level: int


# ── Biometric face verify ───────────────────────────────────


class FaceVerifyRequest(BaseModel):
    img1_path: str = Field(..., description="Path to the first face image")
    img2_path: str = Field(..., description="Path to the second face image")
    model_name: str = Field("ArcFace", description="DeepFace model to use")
    detector_backend: str = Field("retinaface", description="Detection backend")
    distance_metric: str = Field("cosine", description="Distance metric")


class FaceVerifyResponse(BaseModel):
    verified: bool
    distance: float
    threshold: float
    model: str
    detector: str
    distance_metric: str
    liveness_passed: Optional[bool] = None
    raw_response: dict


# ── Liveness ─────────────────────────────────────────────────


class LivenessCheckRequest(BaseModel):
    image_path: str = Field(..., description="Path to the face image to check")


class LivenessCheckResponse(BaseModel):
    passed: bool
    blur_score: float
    face_ratio: float
    checks: List[str]
    reasons: List[str]


# ── Audit ────────────────────────────────────────────────────


class AuditEventResponse(BaseModel):
    id: int
    event_type: str
    actor_did: str
    resource: str
    outcome: str
    detail: str
    timestamp: int
