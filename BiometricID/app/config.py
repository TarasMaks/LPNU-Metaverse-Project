"""Centralised configuration loaded from environment variables / .env file."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Application ──────────────────────────────────────────
    app_title: str = "Biometric Identity Service"
    app_version: str = "1.0.0"
    debug: bool = False

    # ── Database ─────────────────────────────────────────────
    database_url: str = "sqlite:///./biometric_identity.db"

    # ── Security ─────────────────────────────────────────────
    vc_signing_key: str = "INSECURE-DEFAULT-CHANGE-ME"
    template_encryption_key: str = "INSECURE-DEFAULT-CHANGE-ME"
    api_key: str = ""
    rate_limit: str = "60/minute"

    # ── Credential lifetimes ─────────────────────────────────
    challenge_ttl_seconds: int = 300
    vc_ttl_seconds: int = 600

    # ── Blockchain ───────────────────────────────────────────
    web3_provider_url: str = ""
    blockchain_private_key: str = ""
    identity_registry_address: str = ""
    commitment_registry_address: str = ""
    policy_registry_address: str = ""
    audit_log_address: str = ""

    # ── Biometric AI ─────────────────────────────────────────
    deepface_model: str = "ArcFace"
    deepface_detector: str = "retinaface"
    deepface_distance_metric: str = "cosine"
    face_match_threshold: float = 0.40
    liveness_blur_threshold: float = 100.0
    liveness_min_face_ratio: float = 0.05

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


def get_settings() -> Settings:
    return Settings()
