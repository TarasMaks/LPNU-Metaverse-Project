"""Encryption and decryption endpoints."""

from __future__ import annotations

import io

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from PIL import Image

from ..config import settings
from ..diffusion_cipher import DiffusionCipher, compute_hmac, verify_hmac
from ..schemas import DecryptResponse, EncryptResponse
from ..transformer_key import TransformerKeyDerivation

router = APIRouter(prefix="/api/v1", tags=["encryption"])

_tkd = TransformerKeyDerivation()


def _read_image(data: bytes) -> tuple[np.ndarray, str]:
    """Read uploaded bytes into a NumPy array; return (array, format)."""
    img = Image.open(io.BytesIO(data))
    fmt = img.format or "PNG"
    return np.array(img), fmt


def _array_to_png_bytes(arr: np.ndarray) -> bytes:
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@router.post("/encrypt", response_model=EncryptResponse)
async def encrypt_image(
    file: UploadFile = File(...),
    passphrase: str = Form(...),
):
    """Encrypt an uploaded image using Transformer-derived key + diffusion cipher."""
    data = await file.read()
    if len(data) > settings.max_image_size_mb * 1024 * 1024:
        raise HTTPException(413, "Image exceeds maximum allowed size")

    image_array, _ = _read_image(data)
    key = _tkd.derive(passphrase)
    cipher = DiffusionCipher(key)
    encrypted = cipher.encrypt(image_array)

    enc_bytes = _array_to_png_bytes(encrypted)
    tag = compute_hmac(key, enc_bytes)
    filename = f"encrypted_{file.filename or 'image.png'}"

    return EncryptResponse(
        message="Image encrypted successfully",
        hmac_tag=tag,
        original_shape=list(image_array.shape),
        filename=filename,
    )


@router.post("/encrypt/download")
async def encrypt_image_download(
    file: UploadFile = File(...),
    passphrase: str = Form(...),
):
    """Encrypt and return the cipherimage as a downloadable PNG."""
    data = await file.read()
    if len(data) > settings.max_image_size_mb * 1024 * 1024:
        raise HTTPException(413, "Image exceeds maximum allowed size")

    image_array, _ = _read_image(data)
    key = _tkd.derive(passphrase)
    cipher = DiffusionCipher(key)
    encrypted = cipher.encrypt(image_array)

    enc_bytes = _array_to_png_bytes(encrypted)
    tag = compute_hmac(key, enc_bytes)
    filename = f"encrypted_{file.filename or 'image.png'}"

    return StreamingResponse(
        io.BytesIO(enc_bytes),
        media_type="image/png",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-HMAC-Tag": tag,
            "X-Original-Shape": str(list(image_array.shape)),
        },
    )


@router.post("/decrypt", response_model=DecryptResponse)
async def decrypt_image(
    file: UploadFile = File(...),
    passphrase: str = Form(...),
    hmac_tag: str = Form(...),
):
    """Decrypt a cipherimage after verifying its HMAC integrity tag."""
    data = await file.read()
    key = _tkd.derive(passphrase)

    if not verify_hmac(key, data, hmac_tag):
        raise HTTPException(400, "HMAC verification failed — image may be tampered")

    image_array, _ = _read_image(data)
    cipher = DiffusionCipher(key)
    decrypted = cipher.decrypt(image_array)

    return DecryptResponse(
        message="Image decrypted successfully",
        integrity_verified=True,
        filename=f"decrypted_{file.filename or 'image.png'}",
    )


@router.post("/decrypt/download")
async def decrypt_image_download(
    file: UploadFile = File(...),
    passphrase: str = Form(...),
    hmac_tag: str = Form(...),
):
    """Decrypt and return the plaintext image as a downloadable PNG."""
    data = await file.read()
    key = _tkd.derive(passphrase)

    if not verify_hmac(key, data, hmac_tag):
        raise HTTPException(400, "HMAC verification failed — image may be tampered")

    image_array, _ = _read_image(data)
    cipher = DiffusionCipher(key)
    decrypted = cipher.decrypt(image_array)

    dec_bytes = _array_to_png_bytes(decrypted)
    filename = f"decrypted_{file.filename or 'image.png'}"

    return StreamingResponse(
        io.BytesIO(dec_bytes),
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
