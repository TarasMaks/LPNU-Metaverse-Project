"""Tests for the middleware stack (load balancer + webhook handler)."""

from app.middleware_stack import RPCLoadBalancer, WebhookHandler


# ── RPCLoadBalancer ──────────────────────────────────────────


def test_load_balancer_no_endpoints():
    lb = RPCLoadBalancer()
    assert lb.node_count == 0
    assert lb.healthy_count == 0
    assert lb.call("eth_blockNumber") is None


def test_load_balancer_with_endpoints():
    lb = RPCLoadBalancer(endpoints=["http://node1:8545", "http://node2:8545"])
    assert lb.node_count == 2
    assert lb.healthy_count == 2


def test_load_balancer_status():
    lb = RPCLoadBalancer(endpoints=["http://node1:8545"])
    status = lb.get_status()
    assert len(status) == 1
    assert status[0]["url"] == "http://node1:8545"
    assert status[0]["healthy"] is True
    assert status[0]["error_count"] == 0


def test_load_balancer_empty_string_filtered():
    lb = RPCLoadBalancer(endpoints=["http://node1:8545", "", "  "])
    assert lb.node_count == 1


# ── WebhookHandler ───────────────────────────────────────────


def test_webhook_no_auth_token_accepts_all():
    handler = WebhookHandler()
    assert handler.validate_token("") is True
    assert handler.validate_token("anything") is True


def test_webhook_with_auth_token():
    handler = WebhookHandler(auth_token="secret-123")
    assert handler.validate_token("secret-123") is True
    assert handler.validate_token("wrong") is False


def test_webhook_process_event_no_handlers():
    handler = WebhookHandler()
    result = handler.process_event({"event_type": "tx_confirm", "data": {}})
    assert result["event_type"] == "tx_confirm"
    assert result["handlers_invoked"] == 0


def test_webhook_register_and_dispatch():
    handler = WebhookHandler()
    received = []

    def on_confirm(event):
        received.append(event)
        return "ok"

    handler.register_handler("tx_confirm", on_confirm)
    result = handler.process_event({"event_type": "tx_confirm", "tx_hash": "0xabc"})

    assert result["handlers_invoked"] == 1
    assert len(received) == 1
    assert received[0]["tx_hash"] == "0xabc"


def test_webhook_handler_error_captured():
    handler = WebhookHandler()

    def failing_handler(event):
        raise ValueError("test error")

    handler.register_handler("fail_event", failing_handler)
    result = handler.process_event({"event_type": "fail_event"})

    assert result["handlers_invoked"] == 1
    assert result["results"][0]["status"] == "error"
    assert "test error" in result["results"][0]["error"]
