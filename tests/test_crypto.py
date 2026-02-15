"""Unit tests for the crypto module."""

from app.crypto import (
    EncryptedBlob,
    compute_commitment,
    decrypt_template,
    encrypt_template,
    generate_nonce,
    sha256_hex,
)


def test_sha256_hex_deterministic():
    assert sha256_hex("hello") == sha256_hex("hello")
    assert sha256_hex("hello") != sha256_hex("world")


def test_generate_nonce_length():
    n = generate_nonce(8)
    assert len(n) == 16  # hex doubles byte length


def test_generate_nonce_unique():
    a = generate_nonce()
    b = generate_nonce()
    assert a != b


def test_compute_commitment_deterministic():
    c1 = compute_commitment("data", "salt", "v1")
    c2 = compute_commitment("data", "salt", "v1")
    assert c1 == c2


def test_compute_commitment_varies_with_salt():
    c1 = compute_commitment("data", "s1", "v1")
    c2 = compute_commitment("data", "s2", "v1")
    assert c1 != c2


def test_encrypt_decrypt_roundtrip():
    key = "my-test-master-key"
    plaintext = b"biometric-embedding-data-here"
    blob = encrypt_template(plaintext, key)
    recovered = decrypt_template(blob, key)
    assert recovered == plaintext


def test_encrypted_blob_b64_roundtrip():
    key = "key123"
    blob = encrypt_template(b"test-data", key)
    b64 = blob.to_b64()
    restored = EncryptedBlob.from_b64(b64)
    assert decrypt_template(restored, key) == b"test-data"


def test_wrong_key_fails():
    blob = encrypt_template(b"secret", "correct-key")
    try:
        decrypt_template(blob, "wrong-key")
        assert False, "Should have raised"
    except Exception:
        pass
