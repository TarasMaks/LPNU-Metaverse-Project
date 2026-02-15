"""High-level integration tests covering the full enrollment → auth → access flow."""

from __future__ import annotations

import base64
import json


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_full_enrollment_and_auth_flow(client):
    """Enrollment → auth challenge → auth verify → access request."""
    user_id = "user-integration-1"
    template = base64.b64encode(json.dumps([0.1] * 128).encode()).decode()

    # 1. Create DID
    did_resp = client.post("/v1/did", json={"method": "key"})
    assert did_resp.status_code == 200
    did = did_resp.json()["did"]

    # 2. Start enrollment
    start = client.post("/v1/enroll/start", json={"user_id": user_id, "version": "v1"})
    assert start.status_code == 200
    start_data = start.json()
    assert "challenge" in start_data
    assert "salt" in start_data

    # 3. Finish enrollment
    finish = client.post(
        "/v1/enroll/finish",
        json={
            "user_id": user_id,
            "template_data": template,
            "salt": start_data["salt"],
            "version": "v1",
            "storage_uri": "ipfs://test-template",
            "challenge": start_data["challenge"],
        },
    )
    assert finish.status_code == 200
    assert finish.json()["commitment"]

    # 4. Auth challenge
    auth_ch = client.post("/v1/auth/challenge", json={"user_id": user_id})
    assert auth_ch.status_code == 200
    nonce = auth_ch.json()["nonce"]

    # 5. Auth verify (with matching biometric probe)
    auth_v = client.post(
        "/v1/auth/verify",
        json={
            "user_id": user_id,
            "did": did,
            "nonce": nonce,
            "desired_level": 2,
            "template_data": template,
        },
    )
    assert auth_v.status_code == 200
    assert auth_v.json()["vc_jwt"]
    assert auth_v.json()["biometric_verified"] is True
    vc_jwt = auth_v.json()["vc_jwt"]

    # 6. Access request with VC
    access = client.post(
        "/v1/access/request",
        json={
            "did": did,
            "resource": "profile",
            "desired_level": 2,
            "factors": ["wallet-sign", "biometric-proof"],
            "vc_jwt": vc_jwt,
        },
    )
    assert access.status_code == 200
    body = access.json()
    assert "level_required" in body


def test_enrollment_challenge_consumed(client):
    """Challenge should be single-use – second finish with same challenge fails."""
    user_id = "user-consume"
    template = base64.b64encode(b"template-bytes").decode()

    start = client.post("/v1/enroll/start", json={"user_id": user_id}).json()

    # First finish succeeds
    r1 = client.post(
        "/v1/enroll/finish",
        json={
            "user_id": user_id,
            "template_data": template,
            "salt": start["salt"],
            "version": "v1",
            "storage_uri": "",
            "challenge": start["challenge"],
        },
    )
    assert r1.status_code == 200

    # Second finish with same challenge must fail
    r2 = client.post(
        "/v1/enroll/finish",
        json={
            "user_id": user_id,
            "template_data": template,
            "salt": start["salt"],
            "version": "v1",
            "storage_uri": "",
            "challenge": start["challenge"],
        },
    )
    assert r2.status_code == 400


def test_auth_nonce_consumed(client):
    """Auth nonce should be single-use."""
    user_id = "user-nonce"
    template = base64.b64encode(b"t").decode()

    # Enroll
    start = client.post("/v1/enroll/start", json={"user_id": user_id}).json()
    client.post(
        "/v1/enroll/finish",
        json={
            "user_id": user_id,
            "template_data": template,
            "salt": start["salt"],
            "version": "v1",
            "storage_uri": "",
            "challenge": start["challenge"],
        },
    )

    # DID
    did = client.post("/v1/did", json={}).json()["did"]

    # Auth challenge
    nonce = client.post("/v1/auth/challenge", json={"user_id": user_id}).json()["nonce"]

    # First verify (level 1, no biometric probe needed)
    r1 = client.post(
        "/v1/auth/verify",
        json={"user_id": user_id, "did": did, "nonce": nonce, "desired_level": 1},
    )
    assert r1.status_code == 200

    # Second verify with same nonce must fail
    r2 = client.post(
        "/v1/auth/verify",
        json={"user_id": user_id, "did": did, "nonce": nonce, "desired_level": 1},
    )
    assert r2.status_code == 400


def test_biometric_mismatch_rejected(client):
    """Auth must fail when the biometric probe does not match the enrollment template."""
    user_id = "user-mismatch"
    enrolled_template = base64.b64encode(json.dumps([1.0] * 128).encode()).decode()
    different_probe = base64.b64encode(json.dumps([-1.0] * 128).encode()).decode()

    # Enroll
    start = client.post("/v1/enroll/start", json={"user_id": user_id}).json()
    client.post(
        "/v1/enroll/finish",
        json={
            "user_id": user_id,
            "template_data": enrolled_template,
            "salt": start["salt"],
            "version": "v1",
            "storage_uri": "",
            "challenge": start["challenge"],
        },
    )

    did = client.post("/v1/did", json={}).json()["did"]
    nonce = client.post("/v1/auth/challenge", json={"user_id": user_id}).json()["nonce"]

    # Verify with a completely different probe → should be rejected
    r = client.post(
        "/v1/auth/verify",
        json={
            "user_id": user_id,
            "did": did,
            "nonce": nonce,
            "desired_level": 2,
            "template_data": different_probe,
        },
    )
    assert r.status_code == 401
    assert "do not match" in r.json()["detail"]


def test_unenrolled_user_cannot_auth(client):
    r = client.post("/v1/auth/challenge", json={"user_id": "ghost"})
    assert r.status_code == 404


def test_expired_vc_denied(client):
    """Access should be denied when the VC has expired."""
    user_id = "user-expiry"
    template = base64.b64encode(b"t").decode()

    start = client.post("/v1/enroll/start", json={"user_id": user_id}).json()
    client.post(
        "/v1/enroll/finish",
        json={
            "user_id": user_id,
            "template_data": template,
            "salt": start["salt"],
            "version": "v1",
            "storage_uri": "",
            "challenge": start["challenge"],
        },
    )
    did = client.post("/v1/did", json={}).json()["did"]
    nonce = client.post("/v1/auth/challenge", json={"user_id": user_id}).json()["nonce"]

    # Issue a normal VC
    auth_r = client.post(
        "/v1/auth/verify",
        json={"user_id": user_id, "did": did, "nonce": nonce, "desired_level": 1},
    )
    assert auth_r.status_code == 200

    # Directly expire the VC in the database
    import app.database as db_mod

    db = next(db_mod.get_db())
    vc_record = db.query(db_mod.DBVerifiableCredential).filter_by(subject_did=did).first()
    assert vc_record is not None
    vc_record.expires_at = 0  # expired in the past
    db.commit()
    db.close()

    r = client.post(
        "/v1/access/request",
        json={
            "did": did,
            "resource": "profile",
            "desired_level": 1,
            "factors": ["wallet-sign"],
        },
    )
    assert r.status_code == 403
