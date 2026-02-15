"""Unit tests for the Verifiable Credential module."""

import time

from app.vc import issue_vc, verify_vc_token


def test_issue_vc_fields():
    vc = issue_vc(
        subject_did="did:key:abc",
        level=2,
        nonce="n123",
        signing_key="secret",
        biometric_method="face",
        ttl_seconds=600,
    )
    assert vc.subject_did == "did:key:abc"
    assert vc.level == 2
    assert vc.nonce == "n123"
    assert vc.jwt_token
    assert vc.jti


def test_vc_is_valid():
    vc = issue_vc("did:key:x", 1, "n", "key", ttl_seconds=60)
    assert vc.is_valid()


def test_vc_expired():
    vc = issue_vc("did:key:x", 1, "n", "key", ttl_seconds=-1)
    assert not vc.is_valid()


def test_verify_vc_token_valid():
    key = "my-secret"
    vc = issue_vc("did:key:test", 2, "nonce", key)
    payload = verify_vc_token(vc.jwt_token, key)
    assert payload is not None
    assert payload["sub"] == "did:key:test"
    assert payload["vc"]["credentialSubject"]["assuranceLevel"] == 2


def test_verify_vc_token_bad_key():
    vc = issue_vc("did:key:test", 1, "n", "correct-key")
    result = verify_vc_token(vc.jwt_token, "wrong-key")
    assert result is None


def test_verify_vc_token_expired():
    key = "k"
    vc = issue_vc("did:key:test", 1, "n", key, ttl_seconds=-10)
    result = verify_vc_token(vc.jwt_token, key)
    assert result is None  # JWT decode should fail due to exp


def test_vc_jwt_contains_type():
    key = "test"
    vc = issue_vc("did:key:x", 3, "n", key)
    payload = verify_vc_token(vc.jwt_token, key)
    assert "BiometricAssurance" in payload["vc"]["type"]
