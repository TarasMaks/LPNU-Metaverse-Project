# Image Encryption Service — Design Document

## Overview

A secure image transmission service that encrypts images while preserving
**format transparency**: the encrypted output is a valid PNG of the same
dimensions as the input, so it flows through any standard image pipeline
(storage, CDN, HTTP transport) without special handling.

## Architecture

```
Passphrase ──► Transformer Key Derivation ──► 32-byte symmetric key
                                                     │
                                                     ▼
 Plaintext    ┌──────────────────────────┐    Cipherimage
  Image  ───► │  Diffusion Forward Pass  │ ───►  (PNG)
   (PNG)      │  (T iterative steps)     │     + HMAC tag
              └──────────────────────────┘

 Cipherimage  ┌──────────────────────────┐    Plaintext
  + HMAC ───► │  Diffusion Reverse Pass  │ ───►  Image
   + key      │  (T iterative steps)     │      (PNG)
              └──────────────────────────┘
```

## Components

### 1. Transformer Key Derivation (`transformer_key.py`)

A lightweight Transformer encoder that processes the passphrase at byte level:

- **Byte embedding** — each byte of the passphrase is mapped to a learned
  (deterministically seeded) embedding vector.
- **Sinusoidal positional encoding** — preserves ordering information.
- **Multi-head self-attention layers** — mix information across all positions,
  producing a complex non-linear transformation of the secret material.
- **Mean pooling + HKDF-Expand** — the Transformer output is pooled and fed
  through HKDF to produce a fixed-length symmetric key.

The Transformer weights are seeded deterministically from the passphrase via
HKDF, so the same passphrase always produces the same key — no stored state.

### 2. Diffusion Cipher (`diffusion_cipher.py`)

Adapts the forward/reverse diffusion process as a symmetric cipher:

- **Forward (encryption)** — iteratively applies key-conditioned structured
  noise over *T* timesteps via a linear beta schedule.  A small key-seeded
  convolutional network (Mini U-Net) modulates the noise at each step.
- **Reverse (decryption)** — given the same key, reproduces the identical
  noise sequence and subtracts it in reverse order.
- **HMAC-SHA256** — an integrity tag is computed over the cipherimage so the
  recipient can detect tampering before attempting decryption.

### 3. REST API (`app/main.py`, `app/routers/`)

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Service health check |
| `/api/v1/encrypt` | POST | Encrypt image, return metadata + HMAC tag |
| `/api/v1/encrypt/download` | POST | Encrypt image, return cipherimage PNG |
| `/api/v1/decrypt` | POST | Decrypt image, return metadata |
| `/api/v1/decrypt/download` | POST | Decrypt image, return plaintext PNG |

## Security Properties

| Property | Mechanism |
|---|---|
| **Confidentiality** | Diffusion cipher with key-conditioned noise |
| **Integrity** | HMAC-SHA256 tag verified before decryption |
| **Key derivation** | Transformer encoder + HKDF-Expand |
| **Transparency** | Output is same-shape valid PNG |

## Running

```bash
# Local
pip install -r requirements.txt
uvicorn app.main:app --reload

# Docker
docker-compose up --build

# Tests
pytest tests/ -v
```
