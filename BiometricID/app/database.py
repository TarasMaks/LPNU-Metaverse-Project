"""SQLAlchemy ORM models and database session management."""

from __future__ import annotations

import time
from typing import Generator

from sqlalchemy import (
    Column,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from .config import Settings

Base = declarative_base()


# ── ORM Models ───────────────────────────────────────────────


class DBEnrollmentChallenge(Base):
    __tablename__ = "enrollment_challenges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, unique=True, nullable=False, index=True)
    challenge = Column(String, nullable=False)
    salt = Column(String, nullable=False)
    version = Column(String, nullable=False, default="v1")
    created_at = Column(Integer, nullable=False, default=lambda: int(time.time()))


class DBAuthChallenge(Base):
    __tablename__ = "auth_challenges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, unique=True, nullable=False, index=True)
    nonce = Column(String, nullable=False)
    created_at = Column(Integer, nullable=False, default=lambda: int(time.time()))


class DBBiometricTemplate(Base):
    __tablename__ = "biometric_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, unique=True, nullable=False, index=True)
    commitment = Column(String, nullable=False)
    encrypted_template = Column(Text, nullable=False)
    storage_uri = Column(String, nullable=False, default="")
    version = Column(String, nullable=False, default="v1")
    status = Column(String, nullable=False, default="active")
    created_at = Column(Integer, nullable=False, default=lambda: int(time.time()))


class DBVerifiableCredential(Base):
    __tablename__ = "verifiable_credentials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    jti = Column(String, unique=True, nullable=False, index=True)
    subject_did = Column(String, nullable=False, index=True)
    issuer_did = Column(String, nullable=False)
    level = Column(Integer, nullable=False)
    jwt_token = Column(Text, nullable=False)
    issued_at = Column(Integer, nullable=False)
    expires_at = Column(Integer, nullable=False)
    revoked = Column(Integer, nullable=False, default=0)


class DBAuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String, nullable=False, index=True)
    actor_did = Column(String, nullable=False, default="")
    resource = Column(String, nullable=False, default="")
    outcome = Column(String, nullable=False)
    detail = Column(Text, nullable=False, default="")
    ip_address = Column(String, nullable=False, default="")
    timestamp = Column(Integer, nullable=False, default=lambda: int(time.time()))


class DBAccessPolicy(Base):
    __tablename__ = "access_policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    resource = Column(String, nullable=False, index=True)
    level = Column(Integer, nullable=False)
    required_factors = Column(String, nullable=False)
    description = Column(String, nullable=False, default="")


class DBIdentity(Base):
    __tablename__ = "identities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    did = Column(String, unique=True, nullable=False, index=True)
    wallet_address = Column(String, nullable=False, default="")
    public_key_pem = Column(Text, nullable=False)
    created_at = Column(Integer, nullable=False, default=lambda: int(time.time()))


class DBLivenessResult(Base):
    __tablename__ = "liveness_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    passed = Column(Integer, nullable=False)
    blur_score = Column(Float, nullable=False, default=0.0)
    face_ratio = Column(Float, nullable=False, default=0.0)
    detail = Column(Text, nullable=False, default="")
    timestamp = Column(Integer, nullable=False, default=lambda: int(time.time()))


# ── Engine & Session ─────────────────────────────────────────

_engine = None
_SessionLocal = None


def init_db(settings: Settings) -> None:
    """Create engine, session factory, and all tables."""
    global _engine, _SessionLocal
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    _engine = create_engine(settings.database_url, connect_args=connect_args)
    _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=_engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session and closes it after use."""
    if _SessionLocal is None:
        raise RuntimeError("Database not initialised – call init_db() first")
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
