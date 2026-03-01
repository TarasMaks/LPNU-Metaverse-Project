"""Tests for the settlement layer client (without a real provider)."""

from app.settlement import SettlementClient


def test_settlement_disabled_without_provider():
    client = SettlementClient(provider_url="")
    assert not client.is_enabled


def test_settlement_methods_return_none_when_disabled():
    client = SettlementClient(provider_url="")
    assert client.anchor_state_root("root", 100) is None
    assert client.verify_state_root("root") is None
    assert client.mint_identity("0x" + "0" * 40, "commitment") is None
    assert client.verify_identity_token(1) is None
    assert client.register_transaction("tx1", "hash", "0x" + "0" * 40) is None


def test_to_bytes32_deterministic():
    b1 = SettlementClient._to_bytes32("test-value")
    b2 = SettlementClient._to_bytes32("test-value")
    assert b1 == b2
    assert len(b1) == 32


def test_to_bytes32_different_inputs():
    b1 = SettlementClient._to_bytes32("value-a")
    b2 = SettlementClient._to_bytes32("value-b")
    assert b1 != b2
