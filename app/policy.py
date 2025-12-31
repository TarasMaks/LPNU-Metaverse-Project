from __future__ import annotations

from typing import Dict, Iterable, List, Set

from .models import AccessDecision, Policy


def default_policies() -> Dict[int, Policy]:
    return {
        1: Policy(level=1, required_factors={"wallet-sign"}, description="Wallet possession"),
        2: Policy(
            level=2,
            required_factors={"wallet-sign", "biometric-proof"},
            description="Wallet + biometric inherence",
        ),
        3: Policy(
            level=3,
            required_factors={"wallet-sign", "biometric-proof", "device-attestation"},
            description="Wallet + biometric + device attestation",
        ),
        4: Policy(
            level=4,
            required_factors={"wallet-sign", "biometric-proof", "device-attestation", "oob-confirmation"},
            description="High assurance with out-of-band confirmation",
        ),
    }


def evaluate_access(
    desired_level: int,
    presented_factors: Iterable[str],
    policies: Dict[int, Policy] | None = None,
) -> AccessDecision:
    policy_map = policies or default_policies()
    target_policy = policy_map.get(desired_level)
    if not target_policy:
        return AccessDecision(
            granted=False,
            reasons=[f"Unknown policy level {desired_level}"],
            level_required=desired_level,
            level_provided=0,
        )

    factors_set: Set[str] = set(presented_factors)
    missing = target_policy.required_factors - factors_set
    if missing:
        return AccessDecision(
            granted=False,
            reasons=[f"Missing factors: {', '.join(sorted(missing))}"],
            level_required=desired_level,
            level_provided=len(factors_set),
        )

    return AccessDecision(
        granted=True,
        reasons=[f"All factors present for level {desired_level}"],
        level_required=desired_level,
        level_provided=desired_level,
    )


def step_up_if_risky(base_level: int, risk_indicators: List[str]) -> int:
    if not risk_indicators:
        return base_level

    # Simple strategy: each risk indicator nudges one level up to a maximum of 4.
    stepped_level = min(4, base_level + len(risk_indicators))
    return stepped_level
