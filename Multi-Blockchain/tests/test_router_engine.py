"""Tests for the adaptive transaction routing engine."""

from app.router_engine import RouterEngine, RoutingPolicy
from app.schemas import (
    TargetLayer,
    TransactionCriticality,
    TransactionSubmitRequest,
)


def _make_request(**kwargs) -> TransactionSubmitRequest:
    defaults = {
        "payload": "0xdeadbeef",
        "sender": "0x" + "a" * 40,
        "criticality": TransactionCriticality.STANDARD,
        "integrity_requirement": 0.5,
        "data_size_bytes": 0,
        "max_latency_ms": 5000,
        "legal_risk": 0.0,
        "confidentiality": 0.0,
    }
    defaults.update(kwargs)
    return TransactionSubmitRequest(**defaults)


def test_critical_always_settlement():
    engine = RouterEngine()
    req = _make_request(criticality=TransactionCriticality.CRITICAL)
    decision = engine.evaluate(req)
    assert decision.target_layer == TargetLayer.SETTLEMENT
    assert decision.confidence == 1.0


def test_low_always_execution():
    engine = RouterEngine()
    req = _make_request(criticality=TransactionCriticality.LOW)
    decision = engine.evaluate(req)
    assert decision.target_layer == TargetLayer.EXECUTION
    assert decision.confidence == 1.0


def test_high_integrity_routes_to_settlement():
    engine = RouterEngine()
    req = _make_request(
        integrity_requirement=0.95,
        legal_risk=0.8,
        confidentiality=0.7,
        max_latency_ms=30000,
    )
    decision = engine.evaluate(req)
    assert decision.target_layer == TargetLayer.SETTLEMENT


def test_low_integrity_large_data_routes_to_execution():
    engine = RouterEngine()
    req = _make_request(
        integrity_requirement=0.1,
        legal_risk=0.0,
        confidentiality=0.0,
        data_size_bytes=500_000,
        max_latency_ms=500,
    )
    decision = engine.evaluate(req)
    assert decision.target_layer == TargetLayer.EXECUTION


def test_custom_policy_thresholds():
    policy = RoutingPolicy(
        w_integrity=0.5,
        w_latency=0.1,
        w_legal_risk=0.2,
        w_confidentiality=0.1,
        w_data_size=0.1,
    )
    engine = RouterEngine(policy)
    req = _make_request(integrity_requirement=0.9, legal_risk=0.9)
    decision = engine.evaluate(req)
    assert decision.target_layer == TargetLayer.SETTLEMENT


def test_routing_decision_has_cost_and_latency():
    engine = RouterEngine()
    req = _make_request(criticality=TransactionCriticality.CRITICAL)
    decision = engine.evaluate(req)
    assert decision.estimated_cost_wei > 0
    assert decision.estimated_latency_ms > 0


def test_neutral_request_with_zero_data():
    engine = RouterEngine()
    req = _make_request(
        integrity_requirement=0.5,
        legal_risk=0.5,
        confidentiality=0.5,
        max_latency_ms=6000,
        data_size_bytes=0,
    )
    decision = engine.evaluate(req)
    # Should produce a valid decision regardless
    assert decision.target_layer in (TargetLayer.SETTLEMENT, TargetLayer.EXECUTION)
    assert 0.0 <= decision.confidence <= 1.0


def test_max_data_size_favours_execution():
    engine = RouterEngine()
    req = _make_request(
        integrity_requirement=0.3,
        data_size_bytes=2_000_000,
        max_latency_ms=500,
    )
    decision = engine.evaluate(req)
    assert decision.target_layer == TargetLayer.EXECUTION
