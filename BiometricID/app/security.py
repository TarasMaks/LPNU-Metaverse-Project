"""Security middleware and utilities.

Provides:
- API-key authentication dependency
- Input path validation (prevent path-traversal on face-image endpoints)
- Request-rate limiting (via slowapi)
- CORS configuration helper
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader

from .config import Settings, get_settings

logger = logging.getLogger(__name__)

# ── API-key authentication ───────────────────────────────────

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(
    api_key: Optional[str] = Depends(_api_key_header),
    settings: Settings = Depends(get_settings),
) -> Optional[str]:
    """FastAPI dependency that enforces API-key auth when configured.

    If ``settings.api_key`` is empty the check is skipped (open access),
    which is convenient during local development.
    """
    if not settings.api_key:
        return None
    if api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key


# ── Path validation ──────────────────────────────────────────

_SAFE_PATH_RE = re.compile(r"^[\w\-./]+$")
_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}


def validate_image_path(path: str) -> str:
    """Validate that *path* looks like a safe, local image path.

    Raises :class:`HTTPException` on directory traversal attempts or
    disallowed extensions.
    """
    # Block directory traversal
    if ".." in path or path.startswith("/etc") or path.startswith("/proc"):
        raise HTTPException(status_code=400, detail="Path traversal not allowed")

    # Check extension
    _, ext = os.path.splitext(path)
    if ext.lower() not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image extension '{ext}'. Allowed: {_ALLOWED_EXTENSIONS}",
        )

    return path


# ── Rate limiting ────────────────────────────────────────────

def get_rate_limiter():
    """Build a slowapi Limiter instance.

    Imported lazily so the module can be loaded even if slowapi is missing.
    """
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    return Limiter(key_func=get_remote_address)


# ── CORS origins helper ─────────────────────────────────────

DEFAULT_CORS_ORIGINS = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://localhost:8080",
]
