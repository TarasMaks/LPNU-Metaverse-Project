"""Transformer-based cryptographic key derivation.

A lightweight Transformer encoder processes a user-supplied passphrase (or raw
key bytes) and produces a deterministic, high-entropy symmetric key.  The
architecture applies multi-head self-attention over the byte-level
representation of the input, enabling the model to learn complex non-linear
mixing of the secret material — far richer than simple hash-based KDFs.

The model weights are **fixed at initialisation** (seeded from the passphrase
itself via HKDF) so that encryption and decryption are perfectly symmetric:
given the same passphrase the same key is always produced.
"""

from __future__ import annotations

import hashlib
import hmac
import math
from typing import Optional

import numpy as np

from .config import settings


# ---------------------------------------------------------------------------
# Deterministic weight initialisation helpers
# ---------------------------------------------------------------------------

def _hkdf_expand(secret: bytes, info: bytes, length: int) -> bytes:
    """Minimal HKDF-Expand (RFC 5869) using HMAC-SHA256."""
    hash_len = 32
    n = math.ceil(length / hash_len)
    okm = b""
    t = b""
    for i in range(1, n + 1):
        t = hmac.new(secret, t + info + bytes([i]), hashlib.sha256).digest()
        okm += t
    return okm[:length]


def _seed_from_passphrase(passphrase: bytes) -> bytes:
    """Derive a 32-byte master seed from the passphrase."""
    return hashlib.sha256(passphrase).digest()


def _deterministic_weights(seed: bytes, shape: tuple[int, ...], label: str) -> np.ndarray:
    """Generate a reproducible float32 weight matrix from *seed* + *label*.

    Uses HMAC in counter mode with a 4-byte counter (supports arbitrary sizes).
    """
    n_elements = math.prod(shape)
    # Derive a label-specific sub-key
    sub_key = hmac.new(seed, label.encode(), hashlib.sha256).digest()
    block_size = 32
    n_blocks = math.ceil(n_elements / block_size)
    chunks: list[bytes] = []
    for i in range(n_blocks):
        chunks.append(hmac.new(sub_key, i.to_bytes(4, "big"), hashlib.sha256).digest())
    raw = b"".join(chunks)[:n_elements]
    arr = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
    arr = (arr - 127.5) / 73.9  # Map [0, 255] → ~N(0, 1)
    return arr.reshape(shape)


# ---------------------------------------------------------------------------
# Transformer building blocks (pure NumPy — no GPU / framework dependency)
# ---------------------------------------------------------------------------

def _softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    e = np.exp(x - x.max(axis=axis, keepdims=True))
    return e / e.sum(axis=axis, keepdims=True)


def _layer_norm(x: np.ndarray, eps: float = 1e-5) -> np.ndarray:
    mean = x.mean(axis=-1, keepdims=True)
    var = x.var(axis=-1, keepdims=True)
    return (x - mean) / np.sqrt(var + eps)


def _gelu(x: np.ndarray) -> np.ndarray:
    return 0.5 * x * (1.0 + np.tanh(math.sqrt(2.0 / math.pi) * (x + 0.044715 * x ** 3)))


class _MultiHeadAttention:
    """Deterministic multi-head self-attention."""

    def __init__(self, seed: bytes, dim: int, num_heads: int, layer_id: int):
        self.num_heads = num_heads
        self.head_dim = dim // num_heads
        self.dim = dim
        pfx = f"mha_{layer_id}"
        self.Wq = _deterministic_weights(seed, (dim, dim), f"{pfx}_Wq")
        self.Wk = _deterministic_weights(seed, (dim, dim), f"{pfx}_Wk")
        self.Wv = _deterministic_weights(seed, (dim, dim), f"{pfx}_Wv")
        self.Wo = _deterministic_weights(seed, (dim, dim), f"{pfx}_Wo")

    def __call__(self, x: np.ndarray) -> np.ndarray:
        B, T, _ = x.shape
        q = (x @ self.Wq).reshape(B, T, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)
        k = (x @ self.Wk).reshape(B, T, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)
        v = (x @ self.Wv).reshape(B, T, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)
        scale = math.sqrt(self.head_dim)
        attn = _softmax(q @ k.transpose(0, 1, 3, 2) / scale)
        out = (attn @ v).transpose(0, 2, 1, 3).reshape(B, T, self.dim)
        return out @ self.Wo


class _FeedForward:
    def __init__(self, seed: bytes, dim: int, layer_id: int):
        pfx = f"ff_{layer_id}"
        self.W1 = _deterministic_weights(seed, (dim, dim * 4), f"{pfx}_W1")
        self.W2 = _deterministic_weights(seed, (dim * 4, dim), f"{pfx}_W2")

    def __call__(self, x: np.ndarray) -> np.ndarray:
        return _gelu(x @ self.W1) @ self.W2


class _TransformerBlock:
    def __init__(self, seed: bytes, dim: int, num_heads: int, layer_id: int):
        self.attn = _MultiHeadAttention(seed, dim, num_heads, layer_id)
        self.ff = _FeedForward(seed, dim, layer_id)

    def __call__(self, x: np.ndarray) -> np.ndarray:
        x = _layer_norm(x + self.attn(x))
        x = _layer_norm(x + self.ff(x))
        return x


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class TransformerKeyDerivation:
    """Derive a symmetric key from a passphrase using a Transformer encoder.

    The Transformer weights are deterministically seeded from the passphrase so
    that the same passphrase always yields the same key — no stored state.
    """

    def __init__(
        self,
        embed_dim: Optional[int] = None,
        num_heads: Optional[int] = None,
        num_layers: Optional[int] = None,
        key_length: Optional[int] = None,
    ):
        self.embed_dim = embed_dim or settings.transformer_embed_dim
        self.num_heads = num_heads or settings.transformer_num_heads
        self.num_layers = num_layers or settings.transformer_num_layers
        self.key_length = key_length or settings.transformer_key_length

    def derive(self, passphrase: str | bytes) -> bytes:
        if isinstance(passphrase, str):
            passphrase = passphrase.encode("utf-8")

        seed = _seed_from_passphrase(passphrase)

        # Byte-level embedding: each byte → embed_dim vector
        tokens = np.frombuffer(passphrase, dtype=np.uint8)
        # Pad / truncate to fixed length 64
        seq_len = 64
        if len(tokens) < seq_len:
            tokens = np.pad(tokens, (0, seq_len - len(tokens)))
        else:
            tokens = tokens[:seq_len]

        embed_matrix = _deterministic_weights(seed, (256, self.embed_dim), "embed")
        x = embed_matrix[tokens][np.newaxis]  # (1, seq_len, embed_dim)

        # Positional encoding (sinusoidal)
        pos = np.arange(seq_len)[:, np.newaxis]
        div = np.exp(np.arange(0, self.embed_dim, 2) * -(math.log(10000.0) / self.embed_dim))
        pe = np.zeros((seq_len, self.embed_dim), dtype=np.float32)
        pe[:, 0::2] = np.sin(pos * div)
        pe[:, 1::2] = np.cos(pos * div)
        x = x + pe[np.newaxis]

        # Transformer layers
        blocks = [
            _TransformerBlock(seed, self.embed_dim, self.num_heads, i)
            for i in range(self.num_layers)
        ]
        for block in blocks:
            x = block(x)

        # Pool → derive key bytes
        pooled = x.mean(axis=1).flatten()
        raw = pooled.tobytes()
        return _hkdf_expand(seed, raw, self.key_length)
