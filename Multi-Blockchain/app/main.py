"""Application entry-point – assembles the FastAPI app with all middleware,
routers, and startup hooks for the Multi-Blockchain service.

Two-layer architecture:
- Settlement Layer (L1): Ethereum 2.0 / PoS for critical state changes
- Execution Layer (L2): High-throughput chain for operational data
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings, get_settings
from .database import init_db
from .execution import ExecutionClient
from .identity import CanonicalIdentityManager
from .ipfs_storage import IPFSStorage
from .middleware_stack import RPCLoadBalancer, WebhookHandler
from .router_engine import RouterEngine, RoutingPolicy
from .routers import anchoring, identity_routes, storage, transactions, webhooks
from .settlement import SettlementClient

# ── Logging ──────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)

# ── Module-level references ──────────────────────────────────

_settlement_client: SettlementClient | None = None
_execution_client: ExecutionClient | None = None
_ipfs_storage: IPFSStorage | None = None
_rpc_balancer: RPCLoadBalancer | None = None


# ── Lifespan (startup / shutdown) ────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _settlement_client, _execution_client, _ipfs_storage, _rpc_balancer
    settings = get_settings()

    # Initialise database
    init_db(settings)
    logger.info("Database initialised (%s)", settings.database_url)

    # Settlement Layer (L1)
    _settlement_client = SettlementClient(
        provider_url=settings.eth_provider_url,
        private_key=settings.eth_private_key,
        chain_id=settings.eth_chain_id,
        anchor_address=settings.settlement_anchor_address,
        identity_nft_address=settings.identity_nft_address,
        tx_registry_address=settings.transaction_registry_address,
    )

    # Execution Layer (L2)
    _execution_client = ExecutionClient(
        provider_url=settings.l2_provider_url,
        private_key=settings.l2_private_key,
        chain_id=settings.l2_chain_id,
    )

    # IPFS hybrid storage
    _ipfs_storage = IPFSStorage(
        api_url=settings.ipfs_api_url,
        gateway_url=settings.ipfs_gateway_url,
    )

    # RPC load balancer
    rpc_endpoints = [
        e.strip() for e in settings.rpc_endpoints.split(",") if e.strip()
    ]
    _rpc_balancer = RPCLoadBalancer(
        endpoints=rpc_endpoints or None,
        timeout_seconds=settings.rpc_timeout_seconds,
        max_retries=settings.rpc_max_retries,
    )

    # Routing engine
    routing_policy = RoutingPolicy(
        integrity_threshold=settings.default_integrity_threshold,
        latency_threshold_ms=settings.default_latency_threshold_ms,
        max_l2_data_size_bytes=settings.l2_max_data_size_bytes,
    )
    router_engine = RouterEngine(routing_policy)

    # Identity manager
    identity_mgr = CanonicalIdentityManager(
        settlement_client=_settlement_client,
        hash_algorithm=settings.puf_hash_algorithm,
    )

    # Webhook handler
    webhook_handler = WebhookHandler(auth_token=settings.alchemy_notify_token)

    # Inject dependencies into routers
    transactions.set_dependencies(router_engine, _settlement_client, _execution_client)
    identity_routes.set_identity_manager(identity_mgr)
    storage.set_dependencies(_ipfs_storage, _settlement_client)
    anchoring.set_settlement_client(_settlement_client)
    webhooks.set_webhook_handler(webhook_handler)

    logger.info(
        "Multi-Blockchain service started (L1=%s, L2=%s, IPFS=%s, RPC nodes=%d)",
        "enabled" if _settlement_client.is_enabled else "disabled",
        "enabled" if _execution_client.is_enabled else "disabled",
        "connected" if _ipfs_storage.is_connected else "local",
        _rpc_balancer.node_count,
    )

    yield  # application is running

    logger.info("Shutting down…")


# ── App factory ──────────────────────────────────────────────

DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
]


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title=settings.app_title,
        version=settings.app_version,
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=DEFAULT_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Versioned routers ────────────────────────────────────
    app.include_router(transactions.router)
    app.include_router(identity_routes.router)
    app.include_router(storage.router)
    app.include_router(anchoring.router)
    app.include_router(webhooks.router)

    # ── Health endpoint (un-versioned) ───────────────────────
    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "settlement_layer": _settlement_client.is_enabled if _settlement_client else False,
            "execution_layer": _execution_client.is_enabled if _execution_client else False,
            "ipfs": _ipfs_storage.is_connected if _ipfs_storage else False,
            "middleware_nodes": _rpc_balancer.node_count if _rpc_balancer else 0,
        }

    # ── Global exception handler ─────────────────────────────
    @app.exception_handler(Exception)
    async def global_exc_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": str(exc)}},
        )

    return app


# Module-level app instance used by ``uvicorn app.main:app``
app = create_app()
