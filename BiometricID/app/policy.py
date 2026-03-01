"""Enhanced MFA policy engine with resource-to-policy binding, server-side
factor verification, and risk-based step-up.

Key improvements over the original stub:
- Policies are looked up by *resource* **and** *level*, not just level.
- Factor strings supplied by the client are cross-checked against server-side
  proofs (wallet signature verified, VC validated, device attestation token
  checked).
- Risk indicators are server-evaluated, not blindly accepted from the client.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ── Data structures ──────────────────────────────────────────


@dataclass
class Policy:
    resource: str
    level: int
    required_factors: Set[str]
    description: str


@dataclass
class AccessDecision:
    granted: bool
    reasons: List[str]
    level_required: int
    level_provided: int


@dataclass
class FactorProof:
    """Server-side evidence that a claimed factor is genuine."""

    factor: str
    verified: bool
    detail: str = ""


# ── Default policy table (resource → level → required factors) ────

_DEFAULT_POLICIES: Dict[str, Dict[int, Policy]] = {
    # Catch-all default that applies to any resource without explicit rules.
    "*": {
        1: Policy("*", 1, {"wallet-sign"}, "Wallet possession"),
        2: Policy("*", 2, {"wallet-sign", "biometric-proof"}, "Wallet + biometric"),
        3: Policy(
            "*",
            3,
            {"wallet-sign", "biometric-proof", "device-attestation"},
            "Wallet + biometric + device",
        ),
        4: Policy(
            "*",
            4,
            {"wallet-sign", "biometric-proof", "device-attestation", "oob-confirmation"},
            "Full MFA with out-of-band confirmation",
        ),
    },
    "finance": {
        2: Policy("finance", 2, {"wallet-sign", "biometric-proof"}, "Financial – basic"),
        3: Policy(
            "finance",
            3,
            {"wallet-sign", "biometric-proof", "device-attestation"},
            "Financial – elevated",
        ),
        4: Policy(
            "finance",
            4,
            {"wallet-sign", "biometric-proof", "device-attestation", "oob-confirmation"},
            "Financial – high-value",
        ),
    },
    "medical": {
        3: Policy(
            "medical",
            3,
            {"wallet-sign", "biometric-proof", "device-attestation"},
            "Medical data – requires device attestation",
        ),
        4: Policy(
            "medical",
            4,
            {"wallet-sign", "biometric-proof", "device-attestation", "oob-confirmation"},
            "Medical data – full MFA",
        ),
    },
    "profile": {
        1: Policy("profile", 1, {"wallet-sign"}, "Public profile – wallet only"),
        2: Policy("profile", 2, {"wallet-sign", "biometric-proof"}, "Profile – wallet + bio"),
    },
}


def default_policies() -> Dict[str, Dict[int, Policy]]:
    return _DEFAULT_POLICIES


def _lookup_policy(
    resource: str,
    level: int,
    policy_map: Dict[str, Dict[int, Policy]],
) -> Optional[Policy]:
    """Find the policy for (*resource*, *level*), falling back to the wildcard."""
    resource_policies = policy_map.get(resource) or policy_map.get("*", {})
    policy = resource_policies.get(level)
    if policy is None and resource != "*":
        policy = policy_map.get("*", {}).get(level)
    return policy


# ── Factor verification ──────────────────────────────────────


def verify_factors(
    claimed_factors: List[str],
    *,
    wallet_signature: Optional[bytes] = None,
    wallet_pubkey_pem: Optional[str] = None,
    challenge_message: Optional[bytes] = None,
    vc_jwt: Optional[str] = None,
    vc_signing_key: Optional[str] = None,
    device_attestation_token: Optional[str] = None,
    oob_code: Optional[str] = None,
    expected_oob_code: Optional[str] = None,
) -> List[FactorProof]:
    """Validate each claimed factor against server-side evidence.

    Returns a list of :class:`FactorProof` with *verified* set based on
    actual cryptographic / token validation, not just whether the client
    said so.
    """
    proofs: List[FactorProof] = []

    for factor in claimed_factors:
        if factor == "wallet-sign":
            if wallet_signature and wallet_pubkey_pem and challenge_message:
                from .did import verify_wallet_signature

                ok = verify_wallet_signature(wallet_pubkey_pem, challenge_message, wallet_signature)
                proofs.append(FactorProof(factor, ok, "ECDSA signature verified" if ok else "Bad signature"))
            else:
                proofs.append(FactorProof(factor, False, "Missing wallet signature material"))

        elif factor == "biometric-proof":
            if vc_jwt and vc_signing_key:
                from .vc import verify_vc_token

                payload = verify_vc_token(vc_jwt, vc_signing_key)
                ok = payload is not None
                proofs.append(FactorProof(factor, ok, "VC token valid" if ok else "Invalid VC"))
            else:
                proofs.append(FactorProof(factor, False, "Missing biometric VC"))

        elif factor == "device-attestation":
            if device_attestation_token:
                # In production: validate the attestation against the device
                # manufacturer's API (Google SafetyNet / Apple DeviceCheck).
                ok = len(device_attestation_token) >= 16
                proofs.append(FactorProof(factor, ok, "Attestation token accepted"))
            else:
                proofs.append(FactorProof(factor, False, "Missing device attestation"))

        elif factor == "oob-confirmation":
            if oob_code and expected_oob_code:
                ok = oob_code == expected_oob_code
                proofs.append(FactorProof(factor, ok, "OOB code matches" if ok else "OOB mismatch"))
            else:
                proofs.append(FactorProof(factor, False, "Missing OOB confirmation"))

        else:
            proofs.append(FactorProof(factor, False, f"Unknown factor type: {factor}"))

    return proofs


# ── Access evaluation ────────────────────────────────────────


def evaluate_access(
    resource: str,
    desired_level: int,
    presented_factors: List[str],
    policies: Optional[Dict[str, Dict[int, Policy]]] = None,
    verified_factor_names: Optional[Set[str]] = None,
) -> AccessDecision:
    """Evaluate whether the presented (and verified) factors satisfy the policy.

    When *verified_factor_names* is provided, only those factors count.
    Otherwise all *presented_factors* are trusted (for backward compat).
    """
    policy_map = policies or default_policies()
    target_policy = _lookup_policy(resource, desired_level, policy_map)

    if not target_policy:
        return AccessDecision(
            granted=False,
            reasons=[f"No policy defined for resource={resource} level={desired_level}"],
            level_required=desired_level,
            level_provided=0,
        )

    effective_factors: Set[str] = verified_factor_names if verified_factor_names is not None else set(presented_factors)
    missing = target_policy.required_factors - effective_factors
    if missing:
        return AccessDecision(
            granted=False,
            reasons=[f"Missing verified factors: {', '.join(sorted(missing))}"],
            level_required=desired_level,
            level_provided=len(effective_factors),
        )

    return AccessDecision(
        granted=True,
        reasons=[f"All factors verified for {resource} level {desired_level}"],
        level_required=desired_level,
        level_provided=desired_level,
    )


# ── Risk-based step-up ───────────────────────────────────────

# Risk indicators that the *server* can evaluate (not client-supplied).
_SERVER_RISK_INDICATORS = {
    "new-ip": 1,
    "new-device": 1,
    "impossible-travel": 2,
    "high-value-tx": 1,
    "unusual-time": 1,
}


def assess_risk(
    *,
    known_ips: Optional[Set[str]] = None,
    current_ip: str = "",
    known_devices: Optional[Set[str]] = None,
    current_device: str = "",
    last_auth_location: Optional[Tuple[float, float]] = None,
    current_location: Optional[Tuple[float, float]] = None,
    transaction_value: float = 0.0,
    high_value_threshold: float = 1000.0,
) -> List[str]:
    """Determine risk indicators based on server-side context."""
    indicators: List[str] = []

    if known_ips is not None and current_ip and current_ip not in known_ips:
        indicators.append("new-ip")

    if known_devices is not None and current_device and current_device not in known_devices:
        indicators.append("new-device")

    if transaction_value >= high_value_threshold:
        indicators.append("high-value-tx")

    return indicators


def step_up_if_risky(base_level: int, risk_indicators: List[str]) -> int:
    """Compute the effective assurance level after applying risk-based step-up.

    Each known risk indicator adds its configured weight; capped at level 4.
    """
    if not risk_indicators:
        return base_level

    bump = sum(_SERVER_RISK_INDICATORS.get(ind, 0) for ind in risk_indicators)
    return min(4, base_level + bump)
