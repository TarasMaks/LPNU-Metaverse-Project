# LPNU-BiometricID
This repository is intended to publicly share the research results and outcomes of the Embedded AI Lab in Lviv Polytechnic National University.

## Biometric identity design

See [`docs/biometric-identity-design.md`](docs/biometric-identity-design.md) for a high-level plan of a Web3/metaverse biometric identification system that combines AI-based liveness, decentralized identity (DID/VC), policy-driven MFA, blockchain registries, and encrypted off-chain storage.

## Running the proof-of-concept API

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the FastAPI server:
   ```bash
   uvicorn app.main:app --reload
   ```
3. Execute tests:
   ```bash
   pytest
   ```

### Optional: DeepFace-based face verification

The PoC exposes `/biometric/face/verify`, which delegates to the DeepFace library for face comparison (ArcFace + RetinaFace by default). To enable it, ensure system-level dependencies for DeepFace are present and install the Python package:

```bash
pip install -r requirements.txt  # includes deepface
```

If DeepFace is missing at runtime, the endpoint responds with `503` and a descriptive message.
