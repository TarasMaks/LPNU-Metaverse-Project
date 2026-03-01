"""Cryptographic utilities: AES-256-GCM encryption, commitments, key derivation."""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
from dataclasses import dataclass


def generate_nonce(byte_length: int = 16) -> str:
    """Return a cryptographically secure hex nonce."""
    return secrets.token_hex(byte_length)


def sha256_hex(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_commitment(template_data: str, salt: str, version: str) -> str:
    """Commitment = SHA-256(template_data || salt || version)."""
    return sha256_hex(f"{template_data}||{salt}||{version}")


# ── AES-256-GCM envelope encryption for biometric templates ──────────


@dataclass
class EncryptedBlob:
    ciphertext: bytes
    nonce: bytes
    tag: bytes

    def to_b64(self) -> str:
        """Serialise as base-64 for DB / off-chain storage."""
        payload = self.nonce + self.tag + self.ciphertext
        return base64.b64encode(payload).decode()

    @classmethod
    def from_b64(cls, data: str) -> "EncryptedBlob":
        raw = base64.b64decode(data)
        return cls(nonce=raw[:12], tag=raw[12:28], ciphertext=raw[28:])


def _derive_aes_key(master_key: str) -> bytes:
    """Derive a 32-byte AES key from the master key string via SHA-256."""
    return hashlib.sha256(master_key.encode()).digest()


def encrypt_template(plaintext: bytes, master_key: str) -> EncryptedBlob:
    """Encrypt *plaintext* with AES-256-GCM."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = _derive_aes_key(master_key)
    nonce = os.urandom(12)
    aes = AESGCM(key)
    ct = aes.encrypt(nonce, plaintext, None)
    # AESGCM.encrypt appends the 16-byte tag to the ciphertext
    return EncryptedBlob(ciphertext=ct[:-16], nonce=nonce, tag=ct[-16:])


def decrypt_template(blob: EncryptedBlob, master_key: str) -> bytes:
    """Decrypt an AES-256-GCM encrypted blob."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = _derive_aes_key(master_key)
    aes = AESGCM(key)
    ct_with_tag = blob.ciphertext + blob.tag
    return aes.decrypt(blob.nonce, ct_with_tag, None)
