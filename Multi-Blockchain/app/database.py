"""SQLAlchemy ORM models and database session management for Multi-Blockchain."""

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


class DBTransaction(Base):
    """Tracks routed transactions across settlement / execution layers."""

    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tx_id = Column(String, unique=True, nullable=False, index=True)
    sender = Column(String, nullable=False)
    payload_hash = Column(String, nullable=False)
    target_layer = Column(String, nullable=False)  # settlement | execution
    criticality = Column(String, nullable=False, default="standard")
    status = Column(String, nullable=False, default="pending")
    tx_hash = Column(String, nullable=False, default="")
    block_number = Column(Integer, nullable=True)
    anchor_tx_hash = Column(String, nullable=False, default="")
    routing_reason = Column(Text, nullable=False, default="")
    created_at = Column(Integer, nullable=False, default=lambda: int(time.time()))
    updated_at = Column(Integer, nullable=False, default=lambda: int(time.time()))


class DBCanonicalIdentity(Base):
    """PUF-based canonical identity bound to an NFT token."""

    __tablename__ = "canonical_identities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject_id = Column(String, unique=True, nullable=False, index=True)
    did = Column(String, unique=True, nullable=False, index=True)
    wallet_address = Column(String, nullable=False)
    puf_commitment = Column(String, nullable=False)
    token_id = Column(String, nullable=False, default="")
    metadata_uri = Column(String, nullable=False, default="")
    nft_tx_hash = Column(String, nullable=False, default="")
    status = Column(String, nullable=False, default="active")
    created_at = Column(Integer, nullable=False, default=lambda: int(time.time()))


class DBStateAnchor(Base):
    """L2 state roots anchored on the settlement layer."""

    __tablename__ = "state_anchors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    anchor_id = Column(String, unique=True, nullable=False, index=True)
    state_root = Column(String, nullable=False, index=True)
    l2_block_number = Column(Integer, nullable=False)
    l1_tx_hash = Column(String, nullable=False, default="")
    l1_block_number = Column(Integer, nullable=True)
    proof = Column(Text, nullable=False, default="")
    created_at = Column(Integer, nullable=False, default=lambda: int(time.time()))


class DBStoragePin(Base):
    """IPFS pin records with optional on-chain anchor."""

    __tablename__ = "storage_pins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cid = Column(String, unique=True, nullable=False, index=True)
    filename = Column(String, nullable=False, default="")
    size_bytes = Column(Integer, nullable=False, default=0)
    anchor_tx_hash = Column(String, nullable=False, default="")
    created_at = Column(Integer, nullable=False, default=lambda: int(time.time()))


class DBRoutingPolicy(Base):
    """Configurable routing policy rules."""

    __tablename__ = "routing_policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    integrity_threshold = Column(Float, nullable=False, default=0.7)
    latency_threshold_ms = Column(Integer, nullable=False, default=2000)
    legal_risk_threshold = Column(Float, nullable=False, default=0.5)
    confidentiality_threshold = Column(Float, nullable=False, default=0.5)
    max_data_size_bytes = Column(Integer, nullable=False, default=1_048_576)
    description = Column(Text, nullable=False, default="")


class DBWebhookEvent(Base):
    """Incoming webhook events from chain notification services."""

    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String, nullable=False, index=True)
    chain_id = Column(Integer, nullable=False)
    tx_hash = Column(String, nullable=False, index=True)
    block_number = Column(Integer, nullable=False)
    data = Column(Text, nullable=False, default="{}")
    processed = Column(Integer, nullable=False, default=0)
    created_at = Column(Integer, nullable=False, default=lambda: int(time.time()))


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
