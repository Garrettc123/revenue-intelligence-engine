"""
Unit tests for RHNS Symbolic Verifier — Constraint Engine
==========================================================
8 tests covering the core constraint rules.
"""

import os
import json
import tempfile
import pytest
from pathlib import Path

# Adjust import path so tests can find the module when run from repo root
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from rhns.symbolic_verifier import SymbolicVerifier, ConstraintViolation, VerificationResult


def make_verifier(**kwargs) -> SymbolicVerifier:
    """Create a SymbolicVerifier backed by a temp state file."""
    tmp = tempfile.mktemp(suffix=".json")
    defaults = dict(
        state_path=tmp,
        rate_limit_hours=4,
        min_action_value_usd=5.0,
        max_actions_per_cycle=10,
        confidence_floor=0.55,
        cooldown_hours=2,
    )
    defaults.update(kwargs)
    return SymbolicVerifier(**defaults)


# ---------------------------------------------------------------------------
# Test 1: clean action passes all rules
# ---------------------------------------------------------------------------
def test_approve_clean_action(monkeypatch):
    """A fresh action with good confidence and no constraint conflicts is approved."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy")
    v = make_verifier()
    result = v.verify(
        action="RETRY_PAYMENT: Contact customer within 2h. Value: $99.00",
        signal_type="payment_failure",
        urgency="high",
        value_usd=99.0,
        confidence=0.85,
    )
    assert result.approved is True
    assert result.violations == []
    assert result.verification_id.startswith("ver_")


# ---------------------------------------------------------------------------
# Test 2: rate limit blocks the same action fired twice
# ---------------------------------------------------------------------------
def test_rate_limit_blocks_repeat():
    """Firing the same action twice within the rate-limit window blocks the second."""
    v = make_verifier(rate_limit_hours=4)
    action = "RETRY_PAYMENT: Contact customer. Value: $50.00"
    signal_type = "payment_failure"

    first = v.verify(action=action, signal_type=signal_type, urgency="high",
                     value_usd=50.0, confidence=0.9)
    assert first.approved is True

    second = v.verify(action=action, signal_type=signal_type, urgency="high",
                      value_usd=50.0, confidence=0.9)
    assert second.approved is False
    rule_ids = [viol.rule_id for viol in second.violations]
    assert "RATE_LIMIT_001" in rule_ids


# ---------------------------------------------------------------------------
# Test 3: cooldown blocks after failure
# ---------------------------------------------------------------------------
def test_cooldown_blocks_after_failure():
    """enter_cooldown followed by verify returns a hard COOLDOWN violation."""
    v = make_verifier(cooldown_hours=2)
    action = "OUTBOUND_CALL: Escalate churn risk. Value: $200.00"
    signal_type = "churn_risk"

    v.enter_cooldown(action=action, signal_type=signal_type, reason="API timeout")

    result = v.verify(action=action, signal_type=signal_type, urgency="high",
                      value_usd=200.0, confidence=0.8)
    assert result.approved is False
    rule_ids = [viol.rule_id for viol in result.violations]
    assert "COOLDOWN_005" in rule_ids


# ---------------------------------------------------------------------------
# Test 4: source unavailability blocks Stripe action without env key
# ---------------------------------------------------------------------------
def test_source_unavail_blocks_stripe_without_key(monkeypatch):
    """STRIPE action without STRIPE_SECRET_KEY env var fails SOURCE_AVAIL rule."""
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    v = make_verifier()
    result = v.verify(
        action="STRIPE_REFUND: Issue refund for customer. Value: $49.00",
        signal_type="refund_request",
        urgency="high",
        value_usd=49.0,
        confidence=0.9,
    )
    assert result.approved is False
    rule_ids = [viol.rule_id for viol in result.violations]
    assert "SOURCE_AVAIL_004" in rule_ids


# ---------------------------------------------------------------------------
# Test 5: urgency-action compatibility blocks CAMPAIGN on low urgency
# ---------------------------------------------------------------------------
def test_urgency_compat_blocks_campaign_on_low_urgency():
    """A CAMPAIGN action with urgency=low violates URGENCY_COMPAT rule."""
    v = make_verifier()
    result = v.verify(
        action="CAMPAIGN: Launch win-back email series. Value: $300.00",
        signal_type="churn_risk",
        urgency="low",
        value_usd=300.0,
        confidence=0.75,
    )
    assert result.approved is False
    rule_ids = [viol.rule_id for viol in result.violations]
    assert "URGENCY_COMPAT_003" in rule_ids


# ---------------------------------------------------------------------------
# Test 6: low confidence returns soft violation but still approves
# ---------------------------------------------------------------------------
def test_confidence_soft_violation_still_approves():
    """Low confidence produces a soft violation but the action is still approved."""
    v = make_verifier(confidence_floor=0.55)
    result = v.verify(
        action="MONITOR: Watch payment retry. Value: $25.00",
        signal_type="payment_failure",
        urgency="medium",
        value_usd=25.0,
        confidence=0.40,   # below floor
    )
    assert result.approved is True
    soft_violations = [viol for viol in result.violations if viol.severity == "soft"]
    assert any(v.rule_id == "CONF_FLOOR_007" for v in soft_violations)


# ---------------------------------------------------------------------------
# Test 7: budget guard blocks actions after max_actions_per_cycle
# ---------------------------------------------------------------------------
def test_budget_guard_blocks_after_max():
    """After max_actions_per_cycle approvals, the next action is blocked."""
    max_actions = 3
    v = make_verifier(max_actions_per_cycle=max_actions)

    for i in range(max_actions):
        result = v.verify(
            action=f"RETRY_PAYMENT: Customer {i}. Value: $10.00",
            signal_type="payment_failure",
            urgency="high",
            value_usd=10.0,
            confidence=0.9,
        )
        assert result.approved is True, f"Action {i} should be approved"

    # One more — should be blocked
    blocked = v.verify(
        action="RETRY_PAYMENT: Customer overflow. Value: $10.00",
        signal_type="payment_failure",
        urgency="high",
        value_usd=10.0,
        confidence=0.9,
    )
    assert blocked.approved is False
    rule_ids = [viol.rule_id for viol in blocked.violations]
    assert "BUDGET_006" in rule_ids


# ---------------------------------------------------------------------------
# Test 8: repair_suggestion is populated when there are violations
# ---------------------------------------------------------------------------
def test_repair_suggestion_populated(monkeypatch):
    """When a violation occurs, repair_suggestion is a non-empty string."""
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    v = make_verifier()
    result = v.verify(
        action="STRIPE_CHARGE: Retry subscription. Value: $99.00",
        signal_type="payment_failure",
        urgency="high",
        value_usd=99.0,
        confidence=0.8,
    )
    assert result.approved is False
    assert isinstance(result.repair_suggestion, str)
    assert len(result.repair_suggestion) > 0
