# Multi-Blockchain

Multi-Blockchain subproject of the [LPNU-Metaverse-Project](../README.md).

## Overview

Integration of private and public blockchain infrastructures in a decentralised, geographically-distributed information system for adaptive transaction processing and smart contract execution. The architecture uses a two-layer design — a **Settlement Layer** (Ethereum 2.0 / PoS) for critical state changes and an **Execution Layer** (Layer 2) for high-throughput operational data — with a policy-driven adaptive routing engine that balances security, latency, cost, and confidentiality.

| Component | Description |
|---|---|
| **Settlement Layer (L1)** | Ethereum 2.0 / PoS — property registration, legal asset transfers, state-root anchoring |
| **Execution Layer (L2)** | Layer-2 chain — monitoring logs, sensor streams, interim reports |
| **Adaptive Router** | Weighted policy engine that routes transactions to L1 or L2 based on integrity, latency, legal risk, confidentiality |
| **Canonical Identity** | PUF (Physically Unclonable Functions) + biometric binding → ERC-721 NFT on settlement layer |
| **IPFS Storage** | Hybrid model — large data off-chain, CID anchored on-chain |
| **Middleware Stack** | Load-balanced RPC proxy with automatic failover |
| **Webhook Handler** | Event-driven sync via Alchemy Notify for real-time UI updates |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Gateway                       │
│  /v1/transaction  /v1/identity  /v1/storage  /v1/anchor │
└────────┬──────────────┬─────────────┬──────────┬────────┘
         │              │             │          │
    ┌────▼────┐   ┌─────▼─────┐  ┌───▼───┐  ┌──▼──────┐
    │ Routing │   │ Identity  │  │ IPFS  │  │ Anchor  │
    │ Engine  │   │ Manager   │  │ Store │  │ Service │
    └────┬────┘   └─────┬─────┘  └───┬───┘  └──┬──────┘
         │              │            │          │
    ┌────▼──────────────▼────────────▼──────────▼────────┐
    │              Middleware Stack                       │
    │         (RPC Load Balancer + Webhooks)              │
    └────────┬───────────────────────────────┬────────────┘
             │                               │
    ┌────────▼────────┐            ┌─────────▼──────────┐
    │ Settlement (L1) │            │  Execution (L2)    │
    │ Ethereum 2.0    │◄──anchor──►│  Layer-2 Chain     │
    │ PoS consensus   │            │  High throughput   │
    └─────────────────┘            └────────────────────┘
```

## Project Structure

```
app/
├── main.py               # FastAPI app assembly, lifespan hooks
├── config.py             # Pydantic settings (env / .env)
├── schemas.py            # Request / response DTOs
├── database.py           # SQLAlchemy ORM models + session
├── settlement.py         # Settlement Layer (L1) blockchain client
├── execution.py          # Execution Layer (L2) blockchain client
├── router_engine.py      # Adaptive transaction routing engine
├── ipfs_storage.py       # IPFS hybrid storage with local fallback
├── identity.py           # PUF canonical identity + NFT management
├── middleware_stack.py   # RPC load balancer + webhook handler
└── routers/
    ├── transactions.py   # Transaction submit / status endpoints
    ├── identity_routes.py# Canonical identity register / verify
    ├── storage.py        # IPFS pin / resolve endpoints
    ├── anchoring.py      # L2 → L1 state-root anchoring
    └── webhooks.py       # Incoming webhook notifications

contracts/
├── SettlementAnchor.sol      # L2 state-root anchoring on L1
├── CanonicalIdentityNFT.sol  # ERC-721 canonical identity token
└── TransactionRegistry.sol   # Critical transaction audit registry

tests/                    # Comprehensive test suite
docs/                     # Design documentation (Ukrainian)
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Service health + layer connectivity |
| `POST` | `/v1/transaction/submit` | Submit transaction with adaptive routing |
| `GET` | `/v1/transaction/status/{tx_id}` | Query transaction status |
| `POST` | `/v1/identity/register` | Register canonical identity (PUF + NFT) |
| `POST` | `/v1/identity/verify` | Verify PUF biometric response |
| `POST` | `/v1/storage/pin` | Pin data to IPFS, anchor CID on-chain |
| `POST` | `/v1/storage/resolve` | Resolve CID to stored data |
| `POST` | `/v1/anchor/submit` | Anchor L2 state root on L1 |
| `POST` | `/v1/anchor/verify` | Verify state-root anchor |
| `POST` | `/v1/webhook/notify` | Receive chain monitoring events |

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your provider URLs and keys

# 3. Run the service
uvicorn app.main:app --port 8001

# 4. Run tests
pytest tests/ -v
```

## Docker

```bash
# Basic service
docker compose up -d

# With local Ethereum node (Ganache)
docker compose --profile blockchain up -d

# With local IPFS node
docker compose --profile storage up -d
```

## Smart Contracts

| Contract | Purpose |
|---|---|
| `SettlementAnchor` | Anchors L2 state roots on L1 with verification and revocation |
| `CanonicalIdentityNFT` | ERC-721 NFT linked to PUF biometric commitment |
| `TransactionRegistry` | Immutable on-chain registry of critical transactions |

All contracts target Solidity `^0.8.20` and are compatible with Ethereum, Polygon, Base, and Arbitrum.

## License

CC0 1.0 Universal – see [LICENSE](../LICENSE).
