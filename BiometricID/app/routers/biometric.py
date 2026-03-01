"""Face verification and liveness-check endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..audit import record_event
from ..config import Settings, get_settings
from ..database import get_db
from ..deepface_adapter import (
    FaceVerificationResult,
    LivenessResult,
    check_liveness,
    verify_face,
)
from ..schemas import (
    FaceVerifyRequest,
    FaceVerifyResponse,
    LivenessCheckRequest,
    LivenessCheckResponse,
)
from ..security import require_api_key, validate_image_path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/biometric", tags=["Biometric"])


@router.post("/face/verify", response_model=FaceVerifyResponse)
def face_verify(
    payload: FaceVerifyRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _key: str | None = Depends(require_api_key),
) -> FaceVerifyResponse:
    # Validate image paths (prevent path traversal)
    validate_image_path(payload.img1_path)
    validate_image_path(payload.img2_path)

    # Liveness check on both images
    liveness1 = check_liveness(
        payload.img1_path,
        blur_threshold=settings.liveness_blur_threshold,
        min_face_ratio=settings.liveness_min_face_ratio,
    )
    liveness2 = check_liveness(
        payload.img2_path,
        blur_threshold=settings.liveness_blur_threshold,
        min_face_ratio=settings.liveness_min_face_ratio,
    )
    liveness_passed = liveness1.passed and liveness2.passed

    try:
        result: FaceVerificationResult = verify_face(
            payload.img1_path,
            payload.img2_path,
            model_name=payload.model_name or settings.deepface_model,
            detector_backend=payload.detector_backend or settings.deepface_detector,
            distance_metric=payload.distance_metric or settings.deepface_distance_metric,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    record_event(
        db,
        event_type="biometric.face_verify",
        outcome="verified" if result.verified else "not_verified",
        detail=f"distance={result.distance:.4f} liveness={liveness_passed}",
    )

    return FaceVerifyResponse(
        verified=result.verified,
        distance=result.distance,
        threshold=result.threshold,
        model=result.model,
        detector=result.detector,
        distance_metric=result.distance_metric,
        liveness_passed=liveness_passed,
        raw_response=result.raw_response,
    )


@router.post("/liveness", response_model=LivenessCheckResponse)
def liveness_check(
    payload: LivenessCheckRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _key: str | None = Depends(require_api_key),
) -> LivenessCheckResponse:
    validate_image_path(payload.image_path)

    result: LivenessResult = check_liveness(
        payload.image_path,
        blur_threshold=settings.liveness_blur_threshold,
        min_face_ratio=settings.liveness_min_face_ratio,
    )

    record_event(
        db,
        event_type="biometric.liveness",
        outcome="passed" if result.passed else "failed",
        detail=f"blur={result.blur_score:.1f} ratio={result.face_ratio:.3f}",
    )

    return LivenessCheckResponse(
        passed=result.passed,
        blur_score=result.blur_score,
        face_ratio=result.face_ratio,
        checks=result.checks,
        reasons=result.reasons,
    )
