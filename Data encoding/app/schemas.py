"""Pydantic schemas for API request / response models."""

from pydantic import BaseModel, Field


class EncryptRequest(BaseModel):
    passphrase: str = Field(..., min_length=1, description="Passphrase for key derivation")


class EncryptResponse(BaseModel):
    message: str
    hmac_tag: str = Field(..., description="HMAC-SHA256 integrity tag over the cipherimage")
    original_shape: list[int]
    filename: str


class DecryptRequest(BaseModel):
    passphrase: str = Field(..., min_length=1)
    hmac_tag: str = Field(..., description="HMAC tag to verify integrity before decryption")


class DecryptResponse(BaseModel):
    message: str
    integrity_verified: bool
    filename: str


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
