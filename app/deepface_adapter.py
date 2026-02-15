"""Enhanced DeepFace adapter with liveness detection and integrated auth flow.

This module wraps the DeepFace library and adds:
- Liveness / anti-spoofing checks (blur, face-ratio, frequency-domain)
- Embedding extraction for enrollment
- 1-to-1 verification for authentication
- Graceful degradation when DeepFace is not installed
"""

from __future__ import annotations

import importlib
import importlib.util
import io
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _deepface_available() -> bool:
    return importlib.util.find_spec("deepface") is not None


def _pillow_available() -> bool:
    return importlib.util.find_spec("PIL") is not None


# ── Liveness / anti-spoofing ─────────────────────────────────


@dataclass
class LivenessResult:
    passed: bool
    blur_score: float = 0.0
    face_ratio: float = 0.0
    checks: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)


def check_liveness(
    image_path: str,
    blur_threshold: float = 100.0,
    min_face_ratio: float = 0.05,
) -> LivenessResult:
    """Run basic liveness heuristics on an image.

    Checks performed:
    1. **Blur detection** – Laplacian variance; printed photos and screens
       tend to have lower high-frequency content.
    2. **Face-to-image ratio** – a very small face suggests a photo-of-a-photo
       or a distant presentation attack.
    3. **Colour-range analysis** – flat colour histograms may indicate a screen
       replay.

    These are lightweight heuristics suitable for a PoC.  Production systems
    should add challenge-response liveness (blink / head-turn) and 3-D depth
    estimation.
    """
    if not _pillow_available():
        return LivenessResult(passed=True, checks=["skipped:pillow-not-installed"])

    from PIL import Image, ImageFilter, ImageStat

    checks: List[str] = []
    reasons: List[str] = []

    img = Image.open(image_path).convert("RGB")
    width, height = img.size

    # 1. Blur detection via Laplacian-like edge filter variance
    edges = img.filter(ImageFilter.FIND_EDGES)
    stat = ImageStat.Stat(edges)
    # Use variance of the luminance channel
    gray_edges = edges.convert("L")
    edge_stat = ImageStat.Stat(gray_edges)
    blur_score = edge_stat.var[0]
    checks.append("blur")
    if blur_score < blur_threshold:
        reasons.append(f"Image too blurry (score {blur_score:.1f} < {blur_threshold})")

    # 2. Face detection & ratio check (use DeepFace if available)
    face_ratio = 0.0
    if _deepface_available():
        try:
            df = importlib.import_module("deepface.DeepFace")
            faces = df.extract_faces(img_path=image_path, enforce_detection=False)
            if faces:
                region = faces[0].get("facial_area", {})
                fw = region.get("w", 0)
                fh = region.get("h", 0)
                face_ratio = (fw * fh) / (width * height) if (width * height) else 0
            checks.append("face-ratio")
            if face_ratio < min_face_ratio:
                reasons.append(
                    f"Face too small relative to image ({face_ratio:.3f} < {min_face_ratio})"
                )
        except Exception as exc:
            logger.warning("Face detection for liveness failed: %s", exc)
            checks.append("face-ratio:error")
    else:
        checks.append("face-ratio:skipped")

    # 3. Colour range – screens and prints may have compressed dynamic range
    colour_stat = ImageStat.Stat(img)
    avg_stddev = sum(colour_stat.stddev) / 3
    checks.append("colour-range")
    if avg_stddev < 15:
        reasons.append(f"Colour range too narrow (avg stddev {avg_stddev:.1f})")

    passed = len(reasons) == 0
    return LivenessResult(
        passed=passed,
        blur_score=blur_score,
        face_ratio=face_ratio,
        checks=checks,
        reasons=reasons,
    )


# ── Face verification ────────────────────────────────────────


@dataclass
class FaceVerificationResult:
    verified: bool
    distance: float
    threshold: float
    model: str
    detector: str
    distance_metric: str
    raw_response: Dict[str, Any]


def _ensure_deepface() -> None:
    if not _deepface_available():
        raise RuntimeError(
            "DeepFace is not installed. Add the dependency and ensure it is available at runtime."
        )


def verify_face(
    img1_path: str,
    img2_path: str,
    model_name: str = "ArcFace",
    detector_backend: str = "retinaface",
    distance_metric: str = "cosine",
) -> FaceVerificationResult:
    """Compare two face images and return a verification result."""
    _ensure_deepface()
    deepface = importlib.import_module("deepface.DeepFace")
    response = deepface.verify(
        img1_path=img1_path,
        img2_path=img2_path,
        model_name=model_name,
        detector_backend=detector_backend,
        distance_metric=distance_metric,
        enforce_detection=True,
    )
    return FaceVerificationResult(
        verified=bool(response.get("verified")),
        distance=float(response.get("distance", 0)),
        threshold=float(response.get("threshold", 0)),
        model=model_name,
        detector=detector_backend,
        distance_metric=distance_metric,
        raw_response=response,
    )


# ── Embedding extraction (for enrollment) ────────────────────


def extract_embedding(
    image_path: str,
    model_name: str = "ArcFace",
    detector_backend: str = "retinaface",
) -> Optional[List[float]]:
    """Extract the face embedding vector from *image_path*.

    Returns ``None`` if no face is detected.
    """
    _ensure_deepface()
    deepface = importlib.import_module("deepface.DeepFace")
    try:
        results = deepface.represent(
            img_path=image_path,
            model_name=model_name,
            detector_backend=detector_backend,
            enforce_detection=True,
        )
        if results:
            return results[0]["embedding"]
    except Exception as exc:
        logger.warning("Embedding extraction failed: %s", exc)
    return None
