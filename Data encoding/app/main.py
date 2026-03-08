"""FastAPI application — Image Encryption Service.

Provides REST endpoints for encrypting and decrypting images using a
Transformer-based key derivation function and a diffusion-model cipher.
"""

from fastapi import FastAPI

from .config import settings
from .routers import encrypt, health

app = FastAPI(
    title=settings.app_name,
    description=(
        "Secure image transmission service that uses a Transformer-based key "
        "derivation function and a diffusion-model cipher to encrypt images "
        "while preserving format transparency (PNG in → PNG out)."
    ),
    version="1.0.0",
)

app.include_router(health.router)
app.include_router(encrypt.router)
