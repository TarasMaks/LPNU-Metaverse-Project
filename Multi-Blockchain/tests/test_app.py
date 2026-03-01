"""Integration tests for the Multi-Blockchain FastAPI application."""

import base64


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "settlement_layer" in data
    assert "execution_layer" in data
    assert "ipfs" in data
    assert "middleware_nodes" in data


# ── Transaction routing ────────────────────────────────────────


def test_submit_critical_transaction(client):
    resp = client.post("/v1/transaction/submit", json={
        "payload": "0xdeadbeef",
        "sender": "0x" + "a" * 40,
        "criticality": "critical",
        "integrity_requirement": 1.0,
        "max_latency_ms": 30000,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["routing"]["target_layer"] == "settlement"
    assert data["tx_id"]
    assert data["status"] in ("routed", "confirmed")


def test_submit_low_criticality_transaction(client):
    resp = client.post("/v1/transaction/submit", json={
        "payload": "0xcafe",
        "sender": "0x" + "b" * 40,
        "criticality": "low",
        "integrity_requirement": 0.1,
        "max_latency_ms": 500,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["routing"]["target_layer"] == "execution"


def test_submit_standard_transaction(client):
    resp = client.post("/v1/transaction/submit", json={
        "payload": "0x1234",
        "sender": "0x" + "c" * 40,
        "criticality": "standard",
        "integrity_requirement": 0.5,
        "data_size_bytes": 1000,
        "max_latency_ms": 5000,
        "legal_risk": 0.3,
        "confidentiality": 0.2,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["routing"]["target_layer"] in ("settlement", "execution")


def test_get_transaction_status(client):
    # Submit first
    resp = client.post("/v1/transaction/submit", json={
        "payload": "0xaabb",
        "sender": "0x" + "d" * 40,
        "criticality": "low",
    })
    tx_id = resp.json()["tx_id"]

    # Query status
    resp = client.get(f"/v1/transaction/status/{tx_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tx_id"] == tx_id
    assert data["target_layer"] == "execution"


def test_get_nonexistent_transaction(client):
    resp = client.get("/v1/transaction/status/nonexistent")
    assert resp.status_code == 404


# ── Canonical Identity ──────────────────────────────────────


def test_register_identity(client):
    resp = client.post("/v1/identity/register", json={
        "subject_id": "test-subject-1",
        "puf_response": "biometric-puf-data-123",
        "wallet_address": "0x" + "e" * 40,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["did"].startswith("did:puf:")
    assert data["token_id"]
    assert data["puf_commitment"]


def test_register_duplicate_identity(client):
    payload = {
        "subject_id": "dup-subject",
        "puf_response": "puf-data",
        "wallet_address": "0x" + "f" * 40,
    }
    resp1 = client.post("/v1/identity/register", json=payload)
    assert resp1.status_code == 200

    resp2 = client.post("/v1/identity/register", json=payload)
    assert resp2.status_code == 409


def test_verify_identity_correct(client):
    # Register
    client.post("/v1/identity/register", json={
        "subject_id": "verify-subject",
        "puf_response": "correct-puf",
        "wallet_address": "0x" + "1" * 40,
    })

    # Verify with correct PUF
    resp = client.post("/v1/identity/verify", json={
        "subject_id": "verify-subject",
        "puf_response": "correct-puf",
    })
    assert resp.status_code == 200
    assert resp.json()["verified"] is True
    assert resp.json()["confidence"] == 1.0


def test_verify_identity_wrong_puf(client):
    client.post("/v1/identity/register", json={
        "subject_id": "wrong-puf-subject",
        "puf_response": "real-puf",
        "wallet_address": "0x" + "2" * 40,
    })

    resp = client.post("/v1/identity/verify", json={
        "subject_id": "wrong-puf-subject",
        "puf_response": "fake-puf",
    })
    assert resp.status_code == 200
    assert resp.json()["verified"] is False


def test_verify_nonexistent_identity(client):
    resp = client.post("/v1/identity/verify", json={
        "subject_id": "no-such-subject",
        "puf_response": "puf",
    })
    assert resp.status_code == 404


# ── IPFS Storage ────────────────────────────────────────────


def test_pin_and_resolve(client):
    data_b64 = base64.b64encode(b"test storage data").decode()

    # Pin
    resp = client.post("/v1/storage/pin", json={
        "data": data_b64,
        "filename": "test.bin",
        "anchor_on_chain": False,
    })
    assert resp.status_code == 200
    pin_data = resp.json()
    assert pin_data["cid"].startswith("Qm")
    assert pin_data["size_bytes"] == len(b"test storage data")

    # Resolve
    resp = client.post("/v1/storage/resolve", json={
        "cid": pin_data["cid"],
    })
    assert resp.status_code == 200
    resolved = resp.json()
    assert base64.b64decode(resolved["data"]) == b"test storage data"


def test_resolve_unknown_cid(client):
    resp = client.post("/v1/storage/resolve", json={
        "cid": "QmNONEXISTENT",
    })
    assert resp.status_code == 404


# ── State Anchoring ─────────────────────────────────────────


def test_submit_anchor(client):
    resp = client.post("/v1/anchor/submit", json={
        "state_root": "0x" + "ab" * 16,
        "block_number": 12345,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["anchor_id"]
    assert data["state_root"] == "0x" + "ab" * 16
    assert data["l2_block_number"] == 12345


def test_verify_anchor_exists(client):
    # Submit anchor first
    client.post("/v1/anchor/submit", json={
        "state_root": "root-to-verify",
        "block_number": 100,
    })

    # Verify
    resp = client.post("/v1/anchor/verify", json={
        "state_root": "root-to-verify",
    })
    assert resp.status_code == 200
    assert resp.json()["verified"] is True


def test_verify_anchor_not_found(client):
    resp = client.post("/v1/anchor/verify", json={
        "state_root": "nonexistent-root",
    })
    assert resp.status_code == 200
    assert resp.json()["verified"] is False


# ── Webhooks ────────────────────────────────────────────────


def test_webhook_notify(client):
    resp = client.post("/v1/webhook/notify", json={
        "event_type": "tx_confirmed",
        "chain_id": 1,
        "tx_hash": "0x" + "ab" * 32,
        "block_number": 1000,
        "data": {"status": "confirmed"},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "accepted"
    assert data["event_id"] > 0
