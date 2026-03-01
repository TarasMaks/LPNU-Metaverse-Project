"""Tests for PUF-based canonical identity management."""

from app.identity import CanonicalIdentityManager


def test_compute_puf_commitment_deterministic():
    mgr = CanonicalIdentityManager()
    c1 = mgr.compute_puf_commitment("puf-response-xyz", "salt123")
    c2 = mgr.compute_puf_commitment("puf-response-xyz", "salt123")
    assert c1 == c2


def test_compute_puf_commitment_different_salt():
    mgr = CanonicalIdentityManager()
    c1 = mgr.compute_puf_commitment("puf-response", "salt-a")
    c2 = mgr.compute_puf_commitment("puf-response", "salt-b")
    assert c1 != c2


def test_derive_did_format():
    mgr = CanonicalIdentityManager()
    did = mgr.derive_did("some-commitment")
    assert did.startswith("did:puf:")
    assert len(did) == len("did:puf:") + 32


def test_generate_token_id():
    mgr = CanonicalIdentityManager()
    tid = mgr.generate_token_id("did:puf:abc123")
    assert len(tid) == 16
    # Deterministic
    assert tid == mgr.generate_token_id("did:puf:abc123")


def test_register_returns_all_fields():
    mgr = CanonicalIdentityManager()
    result = mgr.register(
        subject_id="user-001",
        puf_response="biometric-puf-data",
        wallet_address="0x" + "a" * 40,
    )
    assert "token_id" in result
    assert "did" in result
    assert result["did"].startswith("did:puf:")
    assert "puf_commitment" in result
    assert "nft_tx_hash" in result
    assert result["nft_tx_hash"] is None  # no settlement client


def test_verify_correct_puf():
    mgr = CanonicalIdentityManager()
    reg = mgr.register("user-002", "puf-secret", "0x" + "b" * 40)

    result = mgr.verify("user-002", "puf-secret", reg["puf_commitment"])
    assert result["verified"] is True
    assert result["confidence"] == 1.0
    assert result["did"] == reg["did"]


def test_verify_wrong_puf():
    mgr = CanonicalIdentityManager()
    reg = mgr.register("user-003", "correct-puf", "0x" + "c" * 40)

    result = mgr.verify("user-003", "wrong-puf", reg["puf_commitment"])
    assert result["verified"] is False
    assert result["confidence"] == 0.0


def test_different_subjects_different_dids():
    mgr = CanonicalIdentityManager()
    r1 = mgr.register("user-a", "puf-a", "0x" + "a" * 40)
    r2 = mgr.register("user-b", "puf-b", "0x" + "b" * 40)
    assert r1["did"] != r2["did"]
    assert r1["token_id"] != r2["token_id"]
