"""Policy-based adaptive transaction routing engine.

Evaluates transaction parameters and determines the optimal execution
environment (settlement vs. execution layer) based on:

- Integrity requirements and irreversibility needs
- Data volume and latency specifications
- Legal dispute risk
- Confidentiality and access restrictions
- Transaction cost / execution time trade-offs

The engine implements a weighted scoring model where each criterion
contributes to a composite settlement-preference score.  Transactions
scoring above the threshold are routed to the settlement layer (L1);
those below are processed on the execution layer (L2).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .schemas import (
    RoutingDecision,
    TargetLayer,
    TransactionCriticality,
    TransactionSubmitRequest,
)

logger = logging.getLogger(__name__)


@dataclass
class RoutingPolicy:
    """Configurable thresholds for the adaptive routing algorithm."""

    integrity_threshold: float = 0.7
    latency_threshold_ms: int = 2000
    legal_risk_threshold: float = 0.5
    confidentiality_threshold: float = 0.5
    max_l2_data_size_bytes: int = 1_048_576  # 1 MB

    # Weights for composite scoring (must sum to 1.0)
    w_integrity: float = 0.30
    w_latency: float = 0.15
    w_legal_risk: float = 0.25
    w_confidentiality: float = 0.15
    w_data_size: float = 0.15

    # Estimated costs (wei) for cost reporting
    l1_base_cost_wei: int = 50_000_000_000_000  # ~0.00005 ETH
    l2_base_cost_wei: int = 1_000_000_000_000  # ~0.000001 ETH

    # Estimated latencies (ms)
    l1_base_latency_ms: int = 12_000  # ~12s block time
    l2_base_latency_ms: int = 500  # sub-second


class RouterEngine:
    """Central routing engine that evaluates transaction parameters and
    selects the target layer for execution.
    """

    def __init__(self, policy: RoutingPolicy | None = None) -> None:
        self._policy = policy or RoutingPolicy()

    @property
    def policy(self) -> RoutingPolicy:
        return self._policy

    def evaluate(self, request: TransactionSubmitRequest) -> RoutingDecision:
        """Evaluate a transaction and return a routing decision.

        The algorithm works as follows:
        1. Override: ``critical`` criticality always goes to settlement.
        2. Override: ``low`` criticality always goes to execution.
        3. For ``standard``: compute a weighted score from the four criteria.
           Score >= 0.5 → settlement; otherwise → execution.
        """
        p = self._policy

        # ── hard overrides ────────────────────────────────────
        if request.criticality == TransactionCriticality.CRITICAL:
            return RoutingDecision(
                target_layer=TargetLayer.SETTLEMENT,
                reason="Critical transaction – routed to settlement layer for maximum security",
                estimated_cost_wei=p.l1_base_cost_wei,
                estimated_latency_ms=p.l1_base_latency_ms,
                confidence=1.0,
            )

        if request.criticality == TransactionCriticality.LOW:
            return RoutingDecision(
                target_layer=TargetLayer.EXECUTION,
                reason="Low-criticality transaction – routed to execution layer for speed",
                estimated_cost_wei=p.l2_base_cost_wei,
                estimated_latency_ms=p.l2_base_latency_ms,
                confidence=1.0,
            )

        # ── weighted composite score for standard transactions ──
        scores = self._compute_criterion_scores(request)
        composite = (
            p.w_integrity * scores["integrity"]
            + p.w_latency * scores["latency"]
            + p.w_legal_risk * scores["legal_risk"]
            + p.w_confidentiality * scores["confidentiality"]
            + p.w_data_size * scores["data_size"]
        )

        if composite >= 0.5:
            return RoutingDecision(
                target_layer=TargetLayer.SETTLEMENT,
                reason=(
                    f"Composite score {composite:.2f} >= 0.50 – "
                    f"settlement layer selected (integrity={scores['integrity']:.2f}, "
                    f"legal_risk={scores['legal_risk']:.2f}, "
                    f"confidentiality={scores['confidentiality']:.2f})"
                ),
                estimated_cost_wei=p.l1_base_cost_wei,
                estimated_latency_ms=p.l1_base_latency_ms,
                confidence=min(composite * 2, 1.0),
            )
        else:
            return RoutingDecision(
                target_layer=TargetLayer.EXECUTION,
                reason=(
                    f"Composite score {composite:.2f} < 0.50 – "
                    f"execution layer selected (latency={scores['latency']:.2f}, "
                    f"data_size={scores['data_size']:.2f})"
                ),
                estimated_cost_wei=p.l2_base_cost_wei,
                estimated_latency_ms=p.l2_base_latency_ms,
                confidence=min((1.0 - composite) * 2, 1.0),
            )

    def _compute_criterion_scores(
        self, request: TransactionSubmitRequest
    ) -> dict[str, float]:
        """Compute normalised [0,1] scores for each routing criterion.

        Higher score = more reason to route to the settlement layer.
        """
        p = self._policy

        # Integrity: direct mapping (already 0-1)
        integrity = request.integrity_requirement

        # Latency: low max_latency → needs fast execution → favour L2 → low score
        if request.max_latency_ms <= 0:
            latency = 0.0
        elif request.max_latency_ms >= p.l1_base_latency_ms:
            latency = 1.0  # can tolerate L1 latency
        else:
            latency = request.max_latency_ms / p.l1_base_latency_ms

        # Legal risk: direct mapping (already 0-1)
        legal_risk = request.legal_risk

        # Confidentiality: higher confidentiality → may prefer private L2, but
        # legally binding → settlement.  We interpret high confidentiality as
        # needing settlement-layer's permissioned validation.
        confidentiality = request.confidentiality

        # Data size: large data → favour L2 off-chain → low score
        if request.data_size_bytes <= 0:
            data_size = 0.5  # neutral
        elif request.data_size_bytes >= p.max_l2_data_size_bytes:
            data_size = 0.0  # too large for any chain, must use L2 + IPFS
        else:
            data_size = 1.0 - (request.data_size_bytes / p.max_l2_data_size_bytes)

        return {
            "integrity": integrity,
            "latency": latency,
            "legal_risk": legal_risk,
            "confidentiality": confidentiality,
            "data_size": data_size,
        }
