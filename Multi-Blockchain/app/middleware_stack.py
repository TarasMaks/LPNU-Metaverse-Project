"""Middleware stack with load-balanced RPC proxy and webhook handler.

Instead of individual blockchain nodes, this module provides a
load-balanced facade over multiple RPC endpoints.  This guarantees
high availability and allows executing RPC queries (e.g. legitimacy
checks) with acceptable latency – critical for systems with millions
of users.

The event-driven architecture uses webhooks (e.g. Alchemy Notify) for
instant UI updates when blockchain state changes.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RPCEndpoint:
    """A single RPC endpoint with health tracking."""

    url: str
    healthy: bool = True
    latency_ms: float = 0.0
    last_check: float = field(default_factory=time.time)
    error_count: int = 0


class RPCLoadBalancer:
    """Round-robin load balancer over multiple JSON-RPC endpoints.

    Automatically marks unhealthy endpoints and retries on fallback
    nodes, ensuring the system can handle millions of concurrent
    legitimacy-check queries.
    """

    def __init__(
        self,
        endpoints: List[str] | None = None,
        timeout_seconds: int = 30,
        max_retries: int = 3,
    ) -> None:
        self._endpoints: List[RPCEndpoint] = []
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._current_index = 0

        if endpoints:
            for url in endpoints:
                url = url.strip()
                if url:
                    self._endpoints.append(RPCEndpoint(url=url))

        if not self._endpoints:
            logger.info("No RPC endpoints configured – load balancer inactive")

    @property
    def node_count(self) -> int:
        return len(self._endpoints)

    @property
    def healthy_count(self) -> int:
        return sum(1 for ep in self._endpoints if ep.healthy)

    def _next_healthy(self) -> Optional[RPCEndpoint]:
        """Select the next healthy endpoint using round-robin."""
        if not self._endpoints:
            return None

        start = self._current_index
        for _ in range(len(self._endpoints)):
            ep = self._endpoints[self._current_index % len(self._endpoints)]
            self._current_index = (self._current_index + 1) % len(self._endpoints)
            if ep.healthy:
                return ep

        # All unhealthy – reset and try first
        for ep in self._endpoints:
            ep.healthy = True
            ep.error_count = 0
        return self._endpoints[0] if self._endpoints else None

    def call(self, method: str, params: list | None = None) -> Optional[Dict[str, Any]]:
        """Execute a JSON-RPC call with automatic failover.

        Tries up to ``max_retries`` different healthy endpoints before
        giving up.
        """
        if not self._endpoints:
            return None

        params = params or []
        last_error: Optional[Exception] = None

        for attempt in range(min(self._max_retries, len(self._endpoints))):
            ep = self._next_healthy()
            if ep is None:
                break

            try:
                result = self._rpc_call(ep, method, params)
                return result
            except Exception as exc:
                last_error = exc
                ep.error_count += 1
                if ep.error_count >= 3:
                    ep.healthy = False
                    logger.warning("Endpoint %s marked unhealthy after %d errors", ep.url, ep.error_count)

        if last_error:
            logger.error("All RPC calls failed: %s", last_error)
        return None

    def _rpc_call(
        self, endpoint: RPCEndpoint, method: str, params: list
    ) -> Dict[str, Any]:
        """Execute a single JSON-RPC request against an endpoint."""
        import httpx

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
        }

        start = time.time()
        resp = httpx.post(
            endpoint.url,
            json=payload,
            timeout=float(self._timeout),
        )
        elapsed_ms = (time.time() - start) * 1000
        endpoint.latency_ms = elapsed_ms
        endpoint.last_check = time.time()

        resp.raise_for_status()
        result = resp.json()

        if "error" in result:
            raise RuntimeError(f"RPC error: {result['error']}")

        return result.get("result", {})

    def get_status(self) -> List[Dict[str, Any]]:
        """Return health status of all endpoints."""
        return [
            {
                "url": ep.url,
                "healthy": ep.healthy,
                "latency_ms": round(ep.latency_ms, 2),
                "error_count": ep.error_count,
            }
            for ep in self._endpoints
        ]


class WebhookHandler:
    """Processes incoming webhook notifications from chain monitoring services.

    Supports event-driven architecture for real-time UI updates when
    blockchain state changes (e.g. Alchemy Notify webhooks).
    """

    def __init__(self, auth_token: str = "") -> None:
        self._auth_token = auth_token
        self._handlers: Dict[str, list] = {}

    def register_handler(self, event_type: str, handler: Any) -> None:
        """Register a callback for a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def validate_token(self, token: str) -> bool:
        """Validate an incoming webhook authentication token."""
        if not self._auth_token:
            return True  # no auth configured
        return token == self._auth_token

    def process_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process an incoming webhook event and dispatch to handlers.

        Returns a summary of the processing result.
        """
        event_type = event_data.get("event_type", "unknown")
        handlers = self._handlers.get(event_type, [])

        results = []
        for handler in handlers:
            try:
                result = handler(event_data)
                results.append({"handler": str(handler), "status": "ok", "result": result})
            except Exception as exc:
                results.append({"handler": str(handler), "status": "error", "error": str(exc)})

        return {
            "event_type": event_type,
            "handlers_invoked": len(handlers),
            "results": results,
        }
