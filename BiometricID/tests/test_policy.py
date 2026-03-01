"""Unit tests for the policy engine."""

from app.policy import (
    assess_risk,
    default_policies,
    evaluate_access,
    step_up_if_risky,
    verify_factors,
)


def test_evaluate_access_profile_level1():
    decision = evaluate_access("profile", 1, ["wallet-sign"])
    assert decision.granted is True


def test_evaluate_access_missing_factor():
    decision = evaluate_access("profile", 2, ["wallet-sign"])
    assert decision.granted is False
    assert "biometric-proof" in decision.reasons[0]


def test_evaluate_access_wildcard_fallback():
    decision = evaluate_access("unknown-resource", 1, ["wallet-sign"])
    assert decision.granted is True  # Falls back to wildcard * policy


def test_evaluate_access_finance_level2():
    decision = evaluate_access("finance", 2, ["wallet-sign", "biometric-proof"])
    assert decision.granted is True


def test_evaluate_access_medical_needs_device():
    decision = evaluate_access("medical", 3, ["wallet-sign", "biometric-proof"])
    assert decision.granted is False
    assert "device-attestation" in decision.reasons[0]


def test_evaluate_access_with_verified_factors():
    decision = evaluate_access(
        "profile",
        2,
        ["wallet-sign", "biometric-proof"],
        verified_factor_names={"biometric-proof"},  # wallet-sign NOT verified
    )
    assert decision.granted is False  # wallet-sign is missing from verified set


def test_step_up_no_indicators():
    assert step_up_if_risky(2, []) == 2


def test_step_up_one_indicator():
    assert step_up_if_risky(2, ["new-ip"]) == 3


def test_step_up_capped_at_4():
    assert step_up_if_risky(3, ["new-ip", "new-device", "impossible-travel"]) == 4


def test_step_up_unknown_indicator_no_bump():
    assert step_up_if_risky(2, ["unknown-risk"]) == 2


def test_assess_risk_new_ip():
    indicators = assess_risk(known_ips={"1.2.3.4"}, current_ip="5.6.7.8")
    assert "new-ip" in indicators


def test_assess_risk_known_ip():
    indicators = assess_risk(known_ips={"1.2.3.4"}, current_ip="1.2.3.4")
    assert "new-ip" not in indicators


def test_assess_risk_high_value():
    indicators = assess_risk(transaction_value=5000, high_value_threshold=1000)
    assert "high-value-tx" in indicators


def test_verify_factors_missing_wallet():
    proofs = verify_factors(["wallet-sign"])
    assert len(proofs) == 1
    assert not proofs[0].verified
    assert "Missing" in proofs[0].detail


def test_verify_factors_biometric_with_vc():
    from app.vc import issue_vc

    key = "test-key"
    vc = issue_vc("did:key:x", 2, "n", key)

    proofs = verify_factors(
        ["biometric-proof"],
        vc_jwt=vc.jwt_token,
        vc_signing_key=key,
    )
    assert proofs[0].verified is True


def test_verify_factors_device_attestation():
    proofs = verify_factors(
        ["device-attestation"],
        device_attestation_token="a-valid-token-16+chars",
    )
    assert proofs[0].verified is True


def test_verify_factors_oob_code_match():
    proofs = verify_factors(
        ["oob-confirmation"],
        oob_code="123456",
        expected_oob_code="123456",
    )
    assert proofs[0].verified is True


def test_verify_factors_oob_code_mismatch():
    proofs = verify_factors(
        ["oob-confirmation"],
        oob_code="wrong",
        expected_oob_code="123456",
    )
    assert proofs[0].verified is False
