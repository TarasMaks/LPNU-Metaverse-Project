from __future__ import annotations

import importlib
import importlib.util
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class FaceVerificationResult:
    verified: bool
    distance: float
    threshold: float
    model: str
    detector: str
    distance_metric: str
    raw_response: Dict[str, Any]


def _ensure_deepface_available() -> None:
    if importlib.util.find_spec("deepface") is None:
        raise RuntimeError("DeepFace is not installed. Add the dependency and ensure it is available at runtime.")


def verify_face(
    img1_path: str,
    img2_path: str,
    model_name: str = "ArcFace",
    detector_backend: str = "retinaface",
    distance_metric: str = "cosine",
) -> FaceVerificationResult:
    _ensure_deepface_available()
    deepface_module = importlib.import_module("deepface.DeepFace")
    response = deepface_module.verify(
        img1_path=img1_path,
        img2_path=img2_path,
        model_name=model_name,
        detector_backend=detector_backend,
        distance_metric=distance_metric,
        enforce_detection=False,
    )
    return FaceVerificationResult(
        verified=bool(response.get("verified")),
        distance=float(response.get("distance")),
        threshold=float(response.get("threshold")),
        model=model_name,
        detector=detector_backend,
        distance_metric=distance_metric,
        raw_response=response,
    )
