"""
Unit tests for RHNS Causal Memory module.
Tests the (signal → action → outcome) feedback loop engine.
"""

import os
import sys
import tempfile
import pytest

# Allow running tests from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rhns.causal_memory import CausalMemory, CausalEntry


@pytest.fixture
def memory(tmp_path):
    """Create a CausalMemory instance backed by a temporary file."""
    return CausalMemory(path=str(tmp_path / "test_memory.json"))


def test_record_creates_entry(memory):
    """record() should create an entry that is retrievable by entry_id."""
    entry_id = memory.record(
        signal_type="payment_failed",
        signal_source="stripe",
        action_taken="RETRY_PAYMENT: Contact customer within 2h",
        action_approved=True,
        value_usd=199.99,
        confidence=0.85,
        cycle_id="cycle-001",
    )
    assert entry_id in memory._entries
    entry = memory._entries[entry_id]
    assert entry.signal_type == "payment_failed"
    assert entry.signal_source == "stripe"
    assert entry.action_approved is True
    assert entry.outcome == "unknown"


def test_resolve_success_boosts_confidence(memory):
    """Resolving as success should increase confidence_updated above confidence_at_decision."""
    entry_id = memory.record(
        signal_type="churn_risk",
        signal_source="hubspot",
        action_taken="RETENTION_SEQUENCE: Fire win-back campaign",
        action_approved=True,
        confidence=0.80,
    )
    original_confidence = memory._entries[entry_id].confidence_at_decision
    memory.resolve(entry_id, "success", "Win-back campaign converted customer")
    updated_confidence = memory._entries[entry_id].confidence_updated
    assert updated_confidence > original_confidence


def test_resolve_failure_reduces_confidence(memory):
    """Resolving as failure should decrease confidence_updated below confidence_at_decision."""
    entry_id = memory.record(
        signal_type="opportunity",
        signal_source="hubspot",
        action_taken="PIPELINE_ADD: Add to HubSpot deal stage",
        action_approved=True,
        confidence=0.75,
    )
    original_confidence = memory._entries[entry_id].confidence_at_decision
    memory.resolve(entry_id, "failure", "Deal was already closed-lost")
    updated_confidence = memory._entries[entry_id].confidence_updated
    assert updated_confidence < original_confidence


def test_recall_returns_resolved_only(memory):
    """recall() should only return entries that have been resolved (not 'unknown')."""
    # Record two entries for same signal_type
    id1 = memory.record(
        signal_type="payment_failed",
        signal_source="stripe",
        action_taken="RETRY_PAYMENT: first attempt",
        action_approved=True,
        confidence=0.90,
    )
    id2 = memory.record(
        signal_type="payment_failed",
        signal_source="stripe",
        action_taken="RETRY_PAYMENT: second attempt",
        action_approved=True,
        confidence=0.85,
    )
    # Resolve only the first
    memory.resolve(id1, "success", "Payment retried successfully")

    recalled = memory.recall("payment_failed")
    assert len(recalled) == 1
    assert recalled[0].entry_id == id1


def test_confidence_adjustment_high_success(memory):
    """With >70% success rate, confidence_adjustment() should return a multiplier > 1.0."""
    signal_type = "upsell"
    # Create and resolve 5 success entries
    for i in range(5):
        eid = memory.record(
            signal_type=signal_type,
            signal_source="stripe",
            action_taken=f"UPSELL_TRIGGER: offer #{i}",
            action_approved=True,
            confidence=0.80,
        )
        memory.resolve(eid, "success", f"Upsell #{i} accepted")

    multiplier = memory.confidence_adjustment(signal_type)
    assert multiplier > 1.0


def test_format_for_reason_layer(memory):
    """format_for_reason_layer() output should contain the signal_type string."""
    signal_type = "revenue_confirmed"
    eid = memory.record(
        signal_type=signal_type,
        signal_source="stripe",
        action_taken="Record in Notion revenue log",
        action_approved=True,
        confidence=1.0,
        value_usd=500.0,
    )
    memory.resolve(eid, "success", "Logged successfully")

    output = memory.format_for_reason_layer(signal_type)
    assert signal_type in output
    assert "SUCCESS" in output
