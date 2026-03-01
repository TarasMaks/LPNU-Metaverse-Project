# LPNU-Metaverse-Project

Research results and outcomes from the Embedded AI Lab at Lviv Polytechnic National University.

## Overview

A multi-project repository for metaverse technologies combining biometric identification, blockchain, and AI. This monorepo hosts multiple subprojects under a single reference.

## Subprojects

| Subproject | Description |
|---|---|
| [**BiometricID**](BiometricID/) | Biometric identification system using AI and blockchain for multi-factor authentication in Web 3.0 and metaverse environments |
| [**Multi-Blockchain**](Multi-Blockchain/) | Multi-blockchain integration layer for cross-chain identity and data interoperability |

## Getting Started

Each subproject is self-contained with its own dependencies, configuration, and documentation. Navigate to the subproject directory for specific instructions:

```bash
# BiometricID
cd BiometricID
pip install -r requirements.txt
pytest tests/ -v

# Multi-Blockchain
cd Multi-Blockchain
pip install -r requirements.txt
pytest tests/ -v
```

## Repository Structure

```
LPNU-Metaverse-Project/
├── BiometricID/            # Biometric identity system
│   ├── app/                # FastAPI application
│   ├── contracts/          # Solidity smart contracts
│   ├── tests/              # Test suite
│   └── docs/               # Design documentation
├── Multi-Blockchain/       # Multi-blockchain integration
│   ├── app/                # Application source code
│   ├── contracts/          # Smart contracts
│   ├── tests/              # Test suite
│   └── docs/               # Documentation
├── .github/workflows/      # CI/CD pipelines
├── LICENSE                 # CC0 1.0 Universal (shared)
└── .gitignore              # Shared git ignore rules
```

## License

CC0 1.0 Universal – see [LICENSE](LICENSE).
