# Data Encoding — Secure Image Encryption Service

A secure image transmission service that encrypts images using **Transformer-based key derivation** and a **diffusion-model cipher**. Encrypted output is a valid PNG of the same dimensions as the input (format transparency), allowing cipherimages to flow through any standard image pipeline — storage, CDNs, HTTP transport — without special handling.

## Table of Contents

- [Key Features](#key-features)
- [Architecture](#architecture)
- [How It Works](#how-it-works)
  - [Transformer Key Derivation](#1-transformer-key-derivation)
  - [Diffusion Cipher](#2-diffusion-cipher)
  - [Integrity Verification](#3-integrity-verification)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Local Installation](#local-installation)
  - [Docker](#docker)
- [API Reference](#api-reference)
  - [Endpoints](#endpoints)
  - [Request / Response Examples](#request--response-examples)
- [Configuration](#configuration)
- [Testing](#testing)
- [Security Properties](#security-properties)

## Key Features

- **Transformer Key Derivation** — multi-head self-attention over byte-level passphrase representation produces high-entropy 32-byte symmetric keys, providing richer non-linear mixing than traditional hash-based KDFs.
- **Diffusion Cipher** — forward/reverse diffusion process repurposed as a symmetric encryption scheme with key-conditioned noise and a Mini U-Net modulation network.
- **Format Transparency** — cipherimages are standard PNGs with the same resolution, channel count, and dtype as the input, compatible with any image pipeline.
- **Integrity Verification** — HMAC-SHA256 tags computed over cipherimage bytes protect against tampering; verification happens before decryption.
- **REST API** — async FastAPI service with encrypt/decrypt endpoints, file upload support, and interactive Swagger documentation.
- **Zero External ML Dependencies** — the Transformer encoder and diffusion cipher are implemented in pure NumPy with no GPU or deep learning framework required.

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

## How It Works

### 1. Transformer Key Derivation

Located in `app/transformer_key.py`, this component converts a user-supplied passphrase into a deterministic 32-byte symmetric key through the following pipeline:

1. **Byte Embedding** — each byte of the passphrase is mapped to a 256-dimensional embedding vector using deterministically seeded weights (via HKDF).
2. **Sinusoidal Positional Encoding** — ordering information is injected into the sequence so the model distinguishes character positions.
3. **Multi-Head Self-Attention (4 layers, 8 heads)** — information is mixed across all positions through stacked Transformer encoder blocks (attention + feed-forward with GELU activation and layer normalization).
4. **Mean Pooling + HKDF-Expand** — the Transformer output is pooled across the sequence dimension and passed through HKDF-Expand (RFC 5869) to produce the final fixed-length key.

All Transformer weights are seeded deterministically from the passphrase itself, so the same passphrase always produces the same key — no stored state or trained model is needed.

### 2. Diffusion Cipher

Located in `app/diffusion_cipher.py`, this component adapts the forward/reverse diffusion process as a symmetric cipher:

- **Keystream Generation** — starting from key-conditioned noise, the diffusion process iteratively applies a linear beta schedule over *T* timesteps (default 50). At each step, a small key-seeded convolutional network (Mini U-Net with 3x3 depthwise kernels) modulates the noise, making the cipher resistant to known-plaintext attacks.
- **Encryption** — the generated keystream is XORed with the plaintext image pixels, producing a visually random cipherimage of identical dimensions.
- **Decryption** — since XOR is its own inverse, applying the same keystream (regenerated from the same key) to the cipherimage recovers the original image exactly.

The noise at each timestep is generated using HMAC-SHA256 in counter mode, transformed from uniform to standard-normal distribution via a rational approximation of the inverse CDF (Abramowitz & Stegun 26.2.23).

### 3. Integrity Verification

Before decryption, the service computes an HMAC-SHA256 tag over the cipherimage bytes and compares it (using constant-time comparison) against the tag provided by the sender. If the tags do not match, decryption is refused and a `400` error is returned. This protects against tampering and ensures that only unmodified cipherimages are processed.

## Project Structure

```
Data encoding/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI application entry point
│   ├── config.py                # Pydantic-based configuration (env vars)
│   ├── schemas.py               # Request/response Pydantic models
│   ├── transformer_key.py       # Transformer-based key derivation
│   ├── diffusion_cipher.py      # Diffusion cipher + HMAC utilities
│   └── routers/
│       ├── __init__.py
│       ├── encrypt.py           # Encrypt/decrypt REST endpoints
│       └── health.py            # Health check endpoint
├── tests/
│   ├── conftest.py              # Shared test fixtures
│   ├── test_app.py              # API integration tests
│   ├── test_diffusion_cipher.py # Diffusion cipher unit tests
│   └── test_transformer_key.py  # Key derivation unit tests
├── docs/
│   └── image-encryption-design.md  # Detailed design document
├── contracts/
│   └── .gitkeep
├── Dockerfile                   # Production container image
├── docker-compose.yml           # Docker Compose orchestration
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## Getting Started

### Prerequisites

- Python 3.11+
- pip

### Local Installation

```bash
# Clone the repository and navigate to the project
cd "Data encoding"

# Install dependencies
pip install -r requirements.txt

# Start the development server
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`. Visit `http://localhost:8000/docs` for the interactive Swagger UI documentation.

### Docker

```bash
# Build and start the service
docker-compose up --build

# The API is exposed on port 8000
curl http://localhost:8000/health
```

The container uses `python:3.11-slim` and installs only the required system libraries (`libjpeg`, `zlib`) for Pillow image processing.

## API Reference

### Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Service health check — returns status, service name, and version |
| `/api/v1/encrypt` | POST | Encrypt an uploaded image; returns JSON with HMAC tag and metadata |
| `/api/v1/encrypt/download` | POST | Encrypt an uploaded image; returns the cipherimage as a downloadable PNG |
| `/api/v1/decrypt` | POST | Decrypt a cipherimage after HMAC verification; returns JSON metadata |
| `/api/v1/decrypt/download` | POST | Decrypt a cipherimage; returns the recovered image as a downloadable PNG |

### Request / Response Examples

**Encrypt an image (JSON response):**

```bash
curl -X POST http://localhost:8000/api/v1/encrypt \
  -F "file=@photo.png" \
  -F "passphrase=my-secret-passphrase"
```

Response:
```json
{
  "message": "Image encrypted successfully",
  "hmac_tag": "a1b2c3d4e5f6...",
  "original_shape": [256, 256, 3],
  "filename": "encrypted_photo.png"
}
```

**Encrypt and download cipherimage:**

```bash
curl -X POST http://localhost:8000/api/v1/encrypt/download \
  -F "file=@photo.png" \
  -F "passphrase=my-secret-passphrase" \
  -o encrypted_photo.png
```

The HMAC tag and original shape are returned in response headers (`X-HMAC-Tag`, `X-Original-Shape`).

**Decrypt a cipherimage (download):**

```bash
curl -X POST http://localhost:8000/api/v1/decrypt/download \
  -F "file=@encrypted_photo.png" \
  -F "passphrase=my-secret-passphrase" \
  -F "hmac_tag=a1b2c3d4e5f6..." \
  -o decrypted_photo.png
```

## Configuration

All settings can be overridden via environment variables prefixed with `ENC_` (or via a `.env` file when using Docker Compose):

| Variable | Default | Description |
|---|---|---|
| `ENC_DEBUG` | `false` | Enable debug mode |
| `ENC_TRANSFORMER_EMBED_DIM` | `256` | Transformer embedding dimension |
| `ENC_TRANSFORMER_NUM_HEADS` | `8` | Number of attention heads |
| `ENC_TRANSFORMER_NUM_LAYERS` | `4` | Number of Transformer encoder layers |
| `ENC_TRANSFORMER_KEY_LENGTH` | `32` | Derived key length in bytes |
| `ENC_DIFFUSION_TIMESTEPS` | `50` | Number of diffusion steps (more = stronger but slower) |
| `ENC_DIFFUSION_BETA_START` | `0.0001` | Beta schedule start value |
| `ENC_DIFFUSION_BETA_END` | `0.02` | Beta schedule end value |
| `ENC_MAX_IMAGE_SIZE_MB` | `20` | Maximum upload size in megabytes |

## Testing

```bash
# Run all tests with verbose output
pytest tests/ -v

# Run specific test modules
pytest tests/test_transformer_key.py -v   # Key derivation tests
pytest tests/test_diffusion_cipher.py -v  # Cipher tests
pytest tests/test_app.py -v               # API integration tests
```

## Security Properties

| Property | Mechanism |
|---|---|
| **Confidentiality** | Diffusion-based keystream XORed with image pixels; keystream is conditioned on the symmetric key via HMAC counter mode + Mini U-Net modulation |
| **Integrity** | HMAC-SHA256 tag computed over cipherimage bytes; constant-time verification before decryption |
| **Key Derivation** | 4-layer Transformer encoder with 8-head self-attention + HKDF-Expand (RFC 5869) |
| **Format Transparency** | Output is a valid PNG with identical dimensions and channel count as the input |
| **Determinism** | Same passphrase always produces the same key and keystream — no stored state or randomness |
| **Known-Plaintext Resistance** | Mini U-Net applies non-linear, key-dependent transformations to the noise at each timestep |

See [docs/image-encryption-design.md](docs/image-encryption-design.md) for the full design document.
