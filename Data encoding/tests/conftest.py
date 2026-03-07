"""Shared test fixtures."""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def sample_image_rgb():
    """8×8 RGB test image with known pixel values."""
    rng = np.random.RandomState(42)
    return rng.randint(0, 256, (8, 8, 3), dtype=np.uint8)


@pytest.fixture()
def sample_image_gray():
    """8×8 grayscale test image."""
    rng = np.random.RandomState(7)
    return rng.randint(0, 256, (8, 8), dtype=np.uint8)
