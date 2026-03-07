# Data Encoding — Secure Image Encryption Service

Secure image transmission method using **Transformer-based key derivation** and
a **diffusion-model cipher** that preserves format transparency (encrypted
output is a valid PNG of the same dimensions as the input).

## Key Features

- **Transformer Key Derivation** — multi-head self-attention over byte-level
  passphrase representation for high-entropy symmetric key generation.
- **Diffusion Cipher** — forward/reverse diffusion process repurposed as a
  symmetric encryption scheme with key-conditioned noise.
- **Format Transparency** — cipherimages are standard PNGs, compatible with any
  image pipeline.
- **Integrity Verification** — HMAC-SHA256 tags protect against tampering.
- **REST API** — FastAPI service with encrypt/decrypt endpoints.

## Quick Start

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then visit `http://localhost:8000/docs` for the interactive API documentation.

## Docker

```bash
docker-compose up --build
```

## Testing

```bash
pytest tests/ -v
```

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check |
| `/api/v1/encrypt` | POST | Encrypt image → JSON metadata + HMAC |
| `/api/v1/encrypt/download` | POST | Encrypt image → PNG download |
| `/api/v1/decrypt` | POST | Decrypt image → JSON metadata |
| `/api/v1/decrypt/download` | POST | Decrypt image → PNG download |

See [docs/image-encryption-design.md](docs/image-encryption-design.md) for
the full design document.
