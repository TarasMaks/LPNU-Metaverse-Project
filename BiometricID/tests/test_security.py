"""Unit tests for the security module."""

import pytest
from fastapi import HTTPException

from app.security import validate_image_path


def test_validate_image_path_safe():
    assert validate_image_path("images/face.jpg") == "images/face.jpg"


def test_validate_image_path_traversal():
    with pytest.raises(HTTPException) as exc_info:
        validate_image_path("../../etc/passwd")
    assert exc_info.value.status_code == 400


def test_validate_image_path_etc():
    with pytest.raises(HTTPException):
        validate_image_path("/etc/shadow")


def test_validate_image_path_bad_extension():
    with pytest.raises(HTTPException) as exc_info:
        validate_image_path("file.exe")
    assert exc_info.value.status_code == 400


def test_validate_image_path_allowed_extensions():
    for ext in (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"):
        assert validate_image_path(f"face{ext}") == f"face{ext}"


def test_api_key_enforcement(client):
    """When API_KEY is empty, requests should succeed without a header."""
    r = client.get("/health")
    assert r.status_code == 200
