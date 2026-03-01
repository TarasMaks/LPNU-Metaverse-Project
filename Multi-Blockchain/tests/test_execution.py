"""Tests for the execution layer client (without a real provider)."""

from app.execution import ExecutionClient


def test_execution_disabled_without_provider():
    client = ExecutionClient(provider_url="")
    assert not client.is_enabled


def test_execution_methods_return_none_when_disabled():
    client = ExecutionClient(provider_url="")
    assert client.submit_data("hash", "0x" + "0" * 40) is None
    assert client.get_latest_block() is None
    assert client.get_transaction_count() is None


def test_to_bytes32_deterministic():
    b1 = ExecutionClient._to_bytes32("test")
    b2 = ExecutionClient._to_bytes32("test")
    assert b1 == b2
    assert len(b1) == 32
