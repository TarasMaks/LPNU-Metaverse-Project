# BiometricID

Biometric Identity subproject of the [LPNU-Metaverse-Project](../README.md).

## Overview

A biometric identification system using AI algorithms and blockchain technology for multi-factor authentication with multiple access levels to personal data in Web 3.0 and metaverse environments.

**Key capabilities:**

| Component | Description |
|---|---|
| **DID / Identity** | ECDSA P-256 key pairs, `did:key` method, wallet binding |
| **Biometric AI** | DeepFace (ArcFace + RetinaFace), liveness detection, anti-spoofing |
| **Verifiable Credentials** | JWT-signed W3C-style VCs with assurance levels |
| **MFA Policy Engine** | Resource-aware policies, server-side factor verification, risk-based step-up |
| **Blockchain** | Solidity contracts for identity, commitment, policy, and audit registries |
| **Encryption** | AES-256-GCM template encryption, KMS key wrapping |
| **Audit** | Structured logging + database audit trail (no PII on-chain) |

## Architecture

See [`docs/biometric-identity-design.md`](docs/biometric-identity-design.md) for the full design document.

```
Client SDK ──► API Gateway (FastAPI v1/) ──► Policy Engine
                    │                            │
                    ├── Biometric AI Service      ├── Risk Assessor
                    ├── DID / VC Issuer           ├── Factor Verifier
                    ├── Blockchain Client ──► EVM Contracts
                    └── Encrypted Storage ──► SQLite / IPFS
```

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and edit environment config
cp .env.example .env

# 3. Start the server
uvicorn app.main:app --reload

# 4. Run tests
pytest tests/ -v
```

### Docker

```bash
docker compose up --build

# With local Ganache blockchain node:
docker compose --profile blockchain up --build
```

## API Endpoints (v1)

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Service health check |
| `/v1/did` | POST | Generate DID with ECDSA key pair |
| `/v1/enroll/start` | POST | Begin biometric enrollment (challenge + salt) |
| `/v1/enroll/finish` | POST | Complete enrollment (encrypt template, compute commitment) |
| `/v1/auth/challenge` | POST | Request auth challenge nonce |
| `/v1/auth/verify` | POST | Verify biometric probe + issue signed VC |
| `/v1/access/request` | POST | Evaluate MFA policy with server-side factor verification |
| `/v1/keys/wrap` | POST | Wrap data encryption key via KMS |
| `/v1/biometric/face/verify` | POST | AI face comparison with liveness check |
| `/v1/biometric/liveness` | POST | Standalone liveness/anti-spoofing check |

## Smart Contracts

Four Solidity contracts in `contracts/` (EVM-compatible, e.g. Polygon/Base/Arbitrum):

- **IdentityRegistry** – DID ↔ wallet mapping, key rotation, revocation
- **BiometricCommitmentRegistry** – SHA-256 template commitments (no raw biometric data on-chain)
- **AccessPolicyRegistry** – On-chain policy hashes bound to resources
- **AuditLog** – Immutable access/auth event log (hashed, no PII)

## Project Structure

```
app/
├── main.py                 # App assembly, middleware, lifespan
├── config.py               # Pydantic Settings (env vars / .env)
├── database.py             # SQLAlchemy ORM models + session
├── schemas.py              # Pydantic request/response DTOs
├── crypto.py               # AES-256-GCM encryption, commitments
├── did.py                  # DID generation with ECDSA keys
├── vc.py                   # JWT Verifiable Credentials
├── policy.py               # Resource-aware MFA policy engine
├── deepface_adapter.py     # Face verification + liveness
├── blockchain.py           # Web3 contract client
├── security.py             # Rate limiting, CORS, path validation
├── audit.py                # Structured audit logging
└── routers/                # Versioned API route handlers
    ├── enrollment.py
    ├── auth.py
    ├── access.py
    ├── biometric.py
    ├── did_routes.py
    └── keys.py
contracts/
├── IdentityRegistry.sol
├── BiometricCommitmentRegistry.sol
├── AccessPolicyRegistry.sol
└── AuditLog.sol
tests/
├── conftest.py             # Shared fixtures, in-memory DB
├── test_app.py             # Integration tests
├── test_crypto.py          # Encryption unit tests
├── test_did.py             # DID generation & signing tests
├── test_vc.py              # VC issuance & verification tests
├── test_policy.py          # Policy engine unit tests
├── test_security.py        # Input validation tests
└── test_blockchain.py      # Blockchain client tests
```

## License

CC0 1.0 Universal – see [LICENSE](../LICENSE).
