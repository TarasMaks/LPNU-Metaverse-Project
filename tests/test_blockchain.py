"""Unit tests for the blockchain client (without a real provider)."""

from app.blockchain import BlockchainClient


def test_blockchain_disabled_without_provider():
    bc = BlockchainClient(provider_url="")
    assert not bc.is_enabled


def test_blockchain_methods_return_none_when_disabled():
    bc = BlockchainClient(provider_url="")
    assert bc.register_identity("did:key:x", "0x" + "0" * 40) is None
    assert bc.store_commitment("user", "commit", "v1", "uri") is None
    assert bc.revoke_commitment("user") is None
    assert bc.record_audit_event("test", "actor", "res", "ok") is None
    assert bc.set_policy("res", 1, "hash", "uri") is None
    assert bc.rotate_key("did", "0x" + "0" * 40) is None
