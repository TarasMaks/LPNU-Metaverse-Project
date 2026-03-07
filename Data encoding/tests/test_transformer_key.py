"""Tests for Transformer key derivation."""

from app.transformer_key import TransformerKeyDerivation


def test_derive_deterministic():
    tkd = TransformerKeyDerivation(num_layers=2)
    k1 = tkd.derive("my-secret-passphrase")
    k2 = tkd.derive("my-secret-passphrase")
    assert k1 == k2


def test_derive_different_passphrases():
    tkd = TransformerKeyDerivation(num_layers=2)
    k1 = tkd.derive("alpha")
    k2 = tkd.derive("beta")
    assert k1 != k2


def test_derive_key_length():
    tkd = TransformerKeyDerivation(key_length=64, num_layers=2)
    key = tkd.derive("test")
    assert len(key) == 64


def test_derive_bytes_input():
    tkd = TransformerKeyDerivation(num_layers=2)
    key = tkd.derive(b"raw-bytes-key")
    assert isinstance(key, bytes)
    assert len(key) == 32
