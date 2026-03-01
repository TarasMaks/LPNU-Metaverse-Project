"""Tests for configuration loading."""

from app.config import Settings, get_settings


def test_default_settings():
    s = get_settings()
    assert s.app_title == "Multi-Blockchain Service"
    assert s.debug is False


def test_settings_has_chain_ids():
    s = Settings()
    assert s.eth_chain_id == 1
    assert s.l2_chain_id == 137


def test_settings_routing_defaults():
    s = Settings()
    assert s.default_integrity_threshold == 0.7
    assert s.default_latency_threshold_ms == 2000
    assert s.l2_max_data_size_bytes == 1_048_576
