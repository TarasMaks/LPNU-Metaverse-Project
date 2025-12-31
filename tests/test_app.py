from fastapi.testclient import TestClient

from app.main import app, store

client = TestClient(app)


def reset_store() -> None:
    store.enrollment_challenges.clear()
    store.auth_challenges.clear()
    store.templates.clear()
    store.credentials.clear()


def test_full_enrollment_and_access_flow():
    reset_store()
    user_id = "user-123"

    start_resp = client.post("/enroll/start", json={"user_id": user_id, "version": "v1"})
    assert start_resp.status_code == 200
    start_data = start_resp.json()

    finish_resp = client.post(
        "/enroll/finish",
        json={
            "user_id": user_id,
            "template_data": "template-bytes",
            "salt": start_data["salt"],
            "version": "v1",
            "storage_uri": "ipfs://template",
            "challenge": start_data["challenge"],
        },
    )
    assert finish_resp.status_code == 200
    commitment = finish_resp.json()["commitment"]
    assert commitment

    auth_challenge = client.post("/auth/challenge", json={"user_id": user_id})
    assert auth_challenge.status_code == 200
    nonce = auth_challenge.json()["nonce"]

    did_resp = client.post("/did")
    did = did_resp.json()["did"]

    auth_verify = client.post(
        "/auth/verify",
        json={"user_id": user_id, "did": did, "nonce": nonce, "desired_level": 2},
    )
    assert auth_verify.status_code == 200
    expires_at = auth_verify.json()["expires_at"]
    assert expires_at > 0

    access_resp = client.post(
        "/access/request",
        json={
            "did": did,
            "resource": "profile",
            "desired_level": 2,
            "factors": ["wallet-sign", "biometric-proof"],
            "risk_indicators": [],
        },
    )
    assert access_resp.status_code == 200
    access_data = access_resp.json()
    assert access_data["granted"] is True


def test_risk_based_step_up_requires_more_factors():
    reset_store()
    user_id = "user-risky"

    start_resp = client.post("/enroll/start", json={"user_id": user_id, "version": "v1"})
    finish_resp = client.post(
        "/enroll/finish",
        json={
            "user_id": user_id,
            "template_data": "template-bytes",
            "salt": start_resp.json()["salt"],
            "version": "v1",
            "storage_uri": "ipfs://template",
            "challenge": start_resp.json()["challenge"],
        },
    )
    assert finish_resp.status_code == 200

    nonce = client.post("/auth/challenge", json={"user_id": user_id}).json()["nonce"]
    did = client.post("/did").json()["did"]
    client.post("/auth/verify", json={"user_id": user_id, "did": did, "nonce": nonce, "desired_level": 2})

    response = client.post(
        "/access/request",
        json={
            "did": did,
            "resource": "finance",
            "desired_level": 2,
            "factors": ["wallet-sign", "biometric-proof"],
            "risk_indicators": ["new-device", "high-value"],
        },
    )

    # With two risk indicators, level steps up to 4; missing factors should deny access.
    assert response.status_code == 200
    body = response.json()
    assert body["granted"] is False
    assert body["level_required"] == 4


def test_face_verify_graceful_failure_when_dependency_missing(monkeypatch):
    reset_store()

    # Simulate missing DeepFace by ensuring find_spec returns None.
    import importlib.util

    monkeypatch.setattr(importlib.util, "find_spec", lambda _: None)

    response = client.post(
        "/biometric/face/verify",
        json={
            "img1_path": "path/to/img1.jpg",
            "img2_path": "path/to/img2.jpg",
        },
    )

    assert response.status_code == 503
    assert "DeepFace is not installed" in response.json()["detail"]
