from __future__ import annotations

from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .deepface_adapter import FaceVerificationResult, verify_face
from .did import generate_did
from .models import (
    AuthChallenge,
    BiometricTemplateRecord,
    EnrollmentChallenge,
    InMemoryStore,
    compute_commitment,
    generate_nonce,
    issue_vc,
)
from .policy import default_policies, evaluate_access, step_up_if_risky

app = FastAPI(title="Biometric Identity PoC", version="0.1.0")
store = InMemoryStore()


class EnrollmentStartRequest(BaseModel):
    user_id: str = Field(..., description="Application user identifier")
    version: str = Field("v1", description="Template version/algorithm hint")


class EnrollmentStartResponse(BaseModel):
    challenge: str
    salt: str
    version: str


class EnrollmentFinishRequest(BaseModel):
    user_id: str
    template_data: str
    salt: str
    version: str
    storage_uri: str
    challenge: str


class EnrollmentFinishResponse(BaseModel):
    commitment: str
    storage_uri: str
    version: str


class AuthChallengeRequest(BaseModel):
    user_id: str


class AuthChallengeResponse(BaseModel):
    nonce: str


class AuthVerifyRequest(BaseModel):
    user_id: str
    did: str
    nonce: str
    desired_level: int = Field(2, description="Requested assurance level for the VC")


class AuthVerifyResponse(BaseModel):
    vc_did: str
    level: int
    expires_at: int


class AccessRequest(BaseModel):
    did: str
    resource: str
    desired_level: int
    factors: List[str]
    risk_indicators: Optional[List[str]] = Field(default_factory=list)


class AccessResponse(BaseModel):
    granted: bool
    reasons: List[str]
    level_required: int
    level_provided: int


class WrapKeyRequest(BaseModel):
    resource: str
    did: str
    policy_level: int


class WrapKeyResponse(BaseModel):
    wrapped_key: str
    policy_level: int


class FaceVerifyRequest(BaseModel):
    img1_path: str = Field(..., description="Path or URI to the first face image")
    img2_path: str = Field(..., description="Path or URI to the second face image")
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
    raw_response: dict


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/did", response_model=dict)
def create_did(method: str = "example") -> dict:
    return {"did": generate_did(method)}


@app.post("/enroll/start", response_model=EnrollmentStartResponse)
def enroll_start(payload: EnrollmentStartRequest) -> EnrollmentStartResponse:
    challenge = generate_nonce(8)
    salt = generate_nonce(4)
    enrollment = EnrollmentChallenge(challenge=challenge, user_id=payload.user_id)
    store.add_enrollment_challenge(enrollment)
    return EnrollmentStartResponse(challenge=challenge, salt=salt, version=payload.version)


@app.post("/enroll/finish", response_model=EnrollmentFinishResponse)
def enroll_finish(payload: EnrollmentFinishRequest) -> EnrollmentFinishResponse:
    expected = store.enrollment_challenges.get(payload.user_id)
    if not expected or expected.challenge != payload.challenge:
        raise HTTPException(status_code=400, detail="Invalid or missing enrollment challenge")

    commitment = compute_commitment(payload.template_data, payload.salt, payload.version)
    record = BiometricTemplateRecord(
        user_id=payload.user_id,
        commitment=commitment,
        storage_uri=payload.storage_uri,
        version=payload.version,
    )
    store.record_template(record)
    return EnrollmentFinishResponse(commitment=commitment, storage_uri=payload.storage_uri, version=payload.version)


@app.post("/auth/challenge", response_model=AuthChallengeResponse)
def auth_challenge(payload: AuthChallengeRequest) -> AuthChallengeResponse:
    if payload.user_id not in store.templates:
        raise HTTPException(status_code=404, detail="User is not enrolled")
    nonce = generate_nonce(8)
    challenge = AuthChallenge(nonce=nonce, user_id=payload.user_id)
    store.add_auth_challenge(challenge)
    return AuthChallengeResponse(nonce=nonce)


@app.post("/auth/verify", response_model=AuthVerifyResponse)
def auth_verify(payload: AuthVerifyRequest) -> AuthVerifyResponse:
    challenge = store.auth_challenges.get(payload.user_id)
    if not challenge or challenge.nonce != payload.nonce:
        raise HTTPException(status_code=400, detail="Invalid auth challenge")

    template = store.templates.get(payload.user_id)
    if not template:
        raise HTTPException(status_code=404, detail="No enrollment found")

    vc = issue_vc(did=payload.did, level=payload.desired_level, nonce=payload.nonce)
    store.store_credential(vc)
    return AuthVerifyResponse(vc_did=vc.subject_did, level=vc.level, expires_at=vc.expires_at)


@app.post("/access/request", response_model=AccessResponse)
def access_request(payload: AccessRequest) -> AccessResponse:
    vc = store.credentials.get(payload.did)
    if not vc or not vc.is_valid():
        raise HTTPException(status_code=403, detail="Missing or expired VC")

    adjusted_level = step_up_if_risky(payload.desired_level, payload.risk_indicators or [])
    if vc.level < adjusted_level:
        raise HTTPException(status_code=403, detail="VC level too low for requested access")

    decision = evaluate_access(adjusted_level, payload.factors, default_policies())
    return AccessResponse(
        granted=decision.granted,
        reasons=decision.reasons,
        level_required=decision.level_required,
        level_provided=decision.level_provided,
    )


@app.post("/keys/wrap", response_model=WrapKeyResponse)
def wrap_key(payload: WrapKeyRequest) -> WrapKeyResponse:
    # In a real system this would call a KMS or proxy re-encryption service.
    wrapped = f"wrapped::{payload.resource}::L{payload.policy_level}::for::{payload.did}"
    return WrapKeyResponse(wrapped_key=wrapped, policy_level=payload.policy_level)


@app.post("/biometric/face/verify", response_model=FaceVerifyResponse)
def face_verify(payload: FaceVerifyRequest) -> FaceVerifyResponse:
    try:
        result: FaceVerificationResult = verify_face(
            payload.img1_path,
            payload.img2_path,
            model_name=payload.model_name,
            detector_backend=payload.detector_backend,
            distance_metric=payload.distance_metric,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return FaceVerifyResponse(
        verified=result.verified,
        distance=result.distance,
        threshold=result.threshold,
        model=result.model,
        detector=result.detector,
        distance_metric=result.distance_metric,
        raw_response=result.raw_response,
    )
