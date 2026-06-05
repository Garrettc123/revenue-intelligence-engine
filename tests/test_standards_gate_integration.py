"""
Integration tests — StandardsGate wired into engine.enforce_standards()
Closes: #2 #3 #4 #5 #6
"""

import json
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from rhns.standards_gate import StandardsGate, PROOF_LOG_PATH, CONF_FLOOR


@pytest.fixture(autouse=True)
def clean_proof_log(tmp_path, monkeypatch):
    import rhns.standards_gate as sg
    monkeypatch.setattr(sg, "PROOF_LOG_PATH", tmp_path / "proof_certificates.jsonl")
    yield tmp_path / "proof_certificates.jsonl"


@pytest.fixture
def gate():
    return StandardsGate()


def test_standards_gate_importable():
    """#2 — StandardsGate can be imported and instantiated without error."""
    from rhns.standards_gate import StandardsGate
    g = StandardsGate()
    assert g is not None


def test_money_action_goes_through_gate(gate):
    """#3 — MONEY domain action passes through evaluate() and returns a verdict."""
    payload = {
        "action": "LOG_REVENUE:Record $299.00 confirmed.",
        "signal_type": "revenue_confirmed",
        "confidence": 0.95,
        "value_usd": 299.0,
        "cycle_id": str(uuid.uuid4()),
    }
    result = gate.evaluate(payload)
    assert "approved" in result
    assert "verdict" in result
    assert "cert_id" in result
    assert result["verdict"] in ("PROVED", "DISPROVED", "SKIPPED")


def test_proved_action_logs_certificate(gate, clean_proof_log):
    """#4 — A PROVED MONEY action writes a ProofCertificate to proof_certificates.jsonl."""
    payload = {
        "action": "LOG_REVENUE:Record $500.00",
        "signal_type": "revenue_confirmed",
        "confidence": 0.98,
        "value_usd": 500.0,
        "cycle_id": str(uuid.uuid4()),
    }
    result = gate.evaluate(payload)
    assert result["verdict"] == "PROVED"
    assert result["approved"] is True
    assert clean_proof_log.exists()
    lines = clean_proof_log.read_text().strip().splitlines()
    assert len(lines) >= 1
    cert = json.loads(lines[-1])
    assert cert["verdict"] == "PROVED"
    assert cert["domain"] == "MONEY"
    assert "cert_id" in cert
    assert "timestamp" in cert


def test_full_3_stage_proved_path(gate, clean_proof_log):
    """#5 — MONEY action passes all 3 stages and returns PROVED."""
    payload = {
        "action": "RETRY_PAYMENT:Contact customer <2h. $299.00",
        "signal_type": "payment_failed",
        "confidence": 0.99,
        "value_usd": 299.0,
        "cycle_id": str(uuid.uuid4()),
    }
    result = gate.evaluate(payload)
    assert result["approved"] is True
    assert result["verdict"] == "PROVED"
    assert result["stage"] == 3
    lines = clean_proof_log.read_text().strip().splitlines()
    cert = json.loads(lines[-1])
    assert cert["stage_reached"] == 3


def test_money_action_fails_confidence_floor(gate, clean_proof_log):
    """#6 — MONEY action with confidence < 0.60 is blocked at Stage 1."""
    payload = {
        "action": "LOG_REVENUE:Record $100.00",
        "signal_type": "revenue_confirmed",
        "confidence": 0.40,
        "value_usd": 100.0,
        "cycle_id": str(uuid.uuid4()),
    }
    result = gate.evaluate(payload)
    assert result["approved"] is False
    assert result["verdict"] == "DISPROVED"
    assert result["stage"] == 1
    assert "STAGE1_FAIL" in result["reason"]


def test_money_action_fails_symbolic_constraint(gate, clean_proof_log):
    """MONEY action with value_usd=0 fails at Stage 2 symbolic check."""
    payload = {
        "action": "LOG_REVENUE:Record $0.00",
        "signal_type": "revenue_confirmed",
        "confidence": 0.95,
        "value_usd": 0.0,
        "cycle_id": str(uuid.uuid4()),
    }
    result = gate.evaluate(payload)
    assert result["approved"] is False
    assert result["verdict"] == "DISPROVED"
    assert result["stage"] == 2


def test_low_stakes_domain_auto_passes(gate, clean_proof_log):
    """DATA/MONITOR domains bypass the gate and get SKIPPED verdict."""
    payload = {
        "action": "SYNC_DATA",
        "signal_type": "data_sync",
        "confidence": 0.50,
        "value_usd": 0.0,
        "cycle_id": str(uuid.uuid4()),
    }
    result = gate.evaluate(payload)
    assert result["approved"] is True
    assert result["verdict"] == "SKIPPED"
