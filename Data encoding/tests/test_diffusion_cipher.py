"""Tests for the diffusion cipher (encrypt / decrypt round-trip)."""

import numpy as np

from app.diffusion_cipher import DiffusionCipher, compute_hmac, verify_hmac
from app.transformer_key import TransformerKeyDerivation


def _make_cipher(passphrase: str = "test-key", timesteps: int = 10) -> DiffusionCipher:
    tkd = TransformerKeyDerivation(num_layers=2)
    key = tkd.derive(passphrase)
    return DiffusionCipher(key, timesteps=timesteps)


def test_encrypt_changes_image(sample_image_rgb):
    cipher = _make_cipher()
    encrypted = cipher.encrypt(sample_image_rgb)
    assert encrypted.shape == sample_image_rgb.shape
    assert encrypted.dtype == np.uint8
    assert not np.array_equal(encrypted, sample_image_rgb)


def test_roundtrip_rgb(sample_image_rgb):
    cipher = _make_cipher(timesteps=5)
    encrypted = cipher.encrypt(sample_image_rgb)
    decrypted = cipher.decrypt(encrypted)
    assert decrypted.shape == sample_image_rgb.shape
    assert decrypted.dtype == np.uint8
    # Allow small rounding tolerance
    diff = np.abs(decrypted.astype(int) - sample_image_rgb.astype(int))
    assert diff.max() <= 2, f"Max pixel difference {diff.max()} exceeds tolerance"


def test_roundtrip_grayscale(sample_image_gray):
    cipher = _make_cipher(timesteps=5)
    encrypted = cipher.encrypt(sample_image_gray)
    decrypted = cipher.decrypt(encrypted)
    diff = np.abs(decrypted.astype(int) - sample_image_gray.astype(int))
    assert diff.max() <= 2


def test_wrong_key_fails(sample_image_rgb):
    cipher_enc = _make_cipher("correct-key", timesteps=5)
    cipher_dec = _make_cipher("wrong-key", timesteps=5)
    encrypted = cipher_enc.encrypt(sample_image_rgb)
    decrypted = cipher_dec.decrypt(encrypted)
    # With the wrong key the output should differ significantly
    diff = np.abs(decrypted.astype(int) - sample_image_rgb.astype(int))
    assert diff.mean() > 5, "Wrong key should not recover the image"


def test_hmac_integrity():
    key = b"secret"
    data = b"some image bytes"
    tag = compute_hmac(key, data)
    assert verify_hmac(key, data, tag)
    assert not verify_hmac(key, data + b"x", tag)
    assert not verify_hmac(b"other", data, tag)
