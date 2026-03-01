"""Application entry-point – assembles the FastAPI app with all middleware,
routers, and startup hooks.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .blockchain import BlockchainClient
from .config import Settings, get_settings
from .database import init_db
from .routers import access, auth, biometric, did_routes, enrollment, keys
from .security import DEFAULT_CORS_ORIGINS

# ── Logging ──────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ────────────────────────────

_blockchain_client: BlockchainClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _blockchain_client
    settings = get_settings()

    # Initialise database
    init_db(settings)
    logger.info("Database initialised (%s)", settings.database_url)

    # Initialise blockchain client
    _blockchain_client = BlockchainClient(
        provider_url=settings.web3_provider_url,
        private_key=settings.blockchain_private_key,
        identity_registry_addr=settings.identity_registry_address,
        commitment_registry_addr=settings.commitment_registry_address,
        policy_registry_addr=settings.policy_registry_address,
        audit_log_addr=settings.audit_log_address,
    )
    # Inject into routers that need it
    did_routes.set_blockchain_client(_blockchain_client)
    enrollment.set_blockchain_client(_blockchain_client)

    yield  # application is running

    logger.info("Shutting down…")


# ── App factory ──────────────────────────────────────────────


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

    # ── Rate limiting ────────────────────────────────────────
    try:
        from slowapi import _rate_limit_exceeded_handler
        from slowapi.errors import RateLimitExceeded

        from .security import get_rate_limiter

        limiter = get_rate_limiter()
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    except ImportError:
        logger.warning("slowapi not installed – rate limiting disabled")

    # ── Versioned routers ────────────────────────────────────
    app.include_router(did_routes.router)
    app.include_router(enrollment.router)
    app.include_router(auth.router)
    app.include_router(access.router)
    app.include_router(biometric.router)
    app.include_router(keys.router)

    # ── Health endpoint (un-versioned) ───────────────────────
    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "blockchain": _blockchain_client.is_enabled if _blockchain_client else False,
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
