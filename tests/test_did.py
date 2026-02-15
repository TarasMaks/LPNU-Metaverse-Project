"""Unit tests for the DID module."""

from app.did import generate_did, sign_message, verify_wallet_signature


def test_generate_did_format():
    doc = generate_did()
    assert doc.did.startswith("did:key:")
    assert len(doc.did) > 10


def test_generate_did_unique():
    d1 = generate_did()
    d2 = generate_did()
    assert d1.did != d2.did


def test_generate_did_has_keys():
    doc = generate_did()
    assert "BEGIN PUBLIC KEY" in doc.public_key_pem
    assert "BEGIN PRIVATE KEY" in doc.private_key_pem


def test_generate_did_wallet_address():
    doc = generate_did()
    assert doc.wallet_address.startswith("0x")
    assert len(doc.wallet_address) == 42


def test_custom_wallet_address():
    doc = generate_did(wallet_address="0xabcdef1234567890abcdef1234567890abcdef12")
    assert doc.wallet_address == "0xabcdef1234567890abcdef1234567890abcdef12"


def test_sign_and_verify():
    doc = generate_did()
    message = b"test-challenge-message"
    signature = sign_message(doc.private_key_pem, message)
    assert verify_wallet_signature(doc.public_key_pem, message, signature)


def test_verify_bad_signature():
    doc = generate_did()
    message = b"message"
    bad_sig = b"\x00" * 64
    assert not verify_wallet_signature(doc.public_key_pem, message, bad_sig)


def test_verify_wrong_message():
    doc = generate_did()
    sig = sign_message(doc.private_key_pem, b"original")
    assert not verify_wallet_signature(doc.public_key_pem, b"tampered", sig)
