"""Centralised configuration loaded from environment variables / .env file.

Supports multi-chain provider URLs for settlement (L1) and execution (L2)
layers, IPFS gateway, middleware stack, and PUF identity settings.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Application ──────────────────────────────────────────
    app_title: str = "Multi-Blockchain Service"
    app_version: str = "1.0.0"
    debug: bool = False

    # ── Database ─────────────────────────────────────────────
    database_url: str = "sqlite:///./multi_blockchain.db"

    # ── Settlement Layer (L1) – Ethereum 2.0 / PoS ─────────
    eth_provider_url: str = ""
    eth_private_key: str = ""
    eth_chain_id: int = 1
    settlement_anchor_address: str = ""
    identity_nft_address: str = ""
    transaction_registry_address: str = ""

    # ── Execution Layer (L2) ─────────────────────────────────
    l2_provider_url: str = ""
    l2_private_key: str = ""
    l2_chain_id: int = 137

    # ── Middleware / RPC ──────────────────────────────────────
    rpc_endpoints: str = ""  # comma-separated fallback endpoints
    rpc_timeout_seconds: int = 30
    rpc_max_retries: int = 3

    # ── IPFS ─────────────────────────────────────────────────
    ipfs_api_url: str = ""
    ipfs_gateway_url: str = "https://ipfs.io/ipfs/"

    # ── Webhooks / Event-driven sync ─────────────────────────
    alchemy_notify_token: str = ""
    webhook_callback_url: str = ""

    # ── PUF Identity ─────────────────────────────────────────
    puf_hash_algorithm: str = "sha256"
    nft_metadata_base_uri: str = ""

    # ── Routing Policy defaults ──────────────────────────────
    default_integrity_threshold: float = 0.7
    default_latency_threshold_ms: int = 2000
    l2_max_data_size_bytes: int = 1_048_576  # 1 MB

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


def get_settings() -> Settings:
    return Settings()
