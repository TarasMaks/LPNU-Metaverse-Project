"""Shared pytest fixtures for the biometric identity service tests."""

from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Create a temp file DB so that in-memory engine reuse is not an issue.
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()

os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"
os.environ["VC_SIGNING_KEY"] = "test-signing-key-for-tests"
os.environ["TEMPLATE_ENCRYPTION_KEY"] = "test-encryption-key-for-tests"
os.environ["CHALLENGE_TTL_SECONDS"] = "300"
os.environ["VC_TTL_SECONDS"] = "600"
os.environ["API_KEY"] = ""  # disable API-key auth in tests

from app.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _reset_db():
    """Drop and recreate all tables between tests for full isolation."""
    import app.database as db_mod

    settings = get_settings()
    db_mod.init_db(settings)
    yield
    # Drop everything after each test
    if db_mod._engine:
        db_mod.Base.metadata.drop_all(bind=db_mod._engine)


@pytest.fixture()
def client():
    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def settings() -> Settings:
    return get_settings()
