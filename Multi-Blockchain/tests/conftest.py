"""Shared pytest fixtures for the Multi-Blockchain service tests."""

from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Create a temp file DB so that in-memory engine reuse is not an issue.
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()

os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"
os.environ["ETH_PROVIDER_URL"] = ""
os.environ["L2_PROVIDER_URL"] = ""
os.environ["IPFS_API_URL"] = ""
os.environ["ALCHEMY_NOTIFY_TOKEN"] = ""
os.environ["DEBUG"] = "false"

from app.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _reset_db():
    """Drop and recreate all tables between tests for full isolation."""
    import app.database as db_mod

    settings = get_settings()
    db_mod.init_db(settings)
    yield
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
