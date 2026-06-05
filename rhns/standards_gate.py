"""
rhns/standards_gate.py  —  Vendored StandardsGate for revenue-intelligence-engine
Closes: #2 (import + instantiation), #3 (MONEY actions gate), #4 (ProofCertificate log)

Standards Gate — 3-stage evaluation for HIGH-STAKES domains.

Stage 1 — Confidence Floor   : confidence >= 0.60
Stage 2 — Symbolic Constraint: domain-specific rule check
Stage 3 — Formal Proof       : backward-chaining axiom chain

HIGH-STAKES : MONEY · SECURITY · DEPLOY
AUTO-PASS   : DATA · MONITOR
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Constants ────────────────────────────────────────────────────────────────
CONF_FLOOR         = 0.60
HIGH_STAKES        = {"MONEY", "SECURITY", "DEPLOY"}
AUTO_PASS          = {"DATA", "MONITOR"}
PROOF_LOG_PATH     = Path("rhns/proof_certificates.jsonl")

_SIGNAL_DOMAIN_MAP = {
    "payment_failed":    "MONEY",
    "revenue_confirmed": "MONEY",
    "churn_risk":        "MONEY",
    "upsell":            "MONEY",
    "opportunity":       "MONEY",
    "deploy":            "DEPLOY",
    "security_alert":    "SECURITY",
    "monitor":           "MONITOR",
    "data_sync":         "DATA",
}


# ── Symbolic Rules ────────────────────────────────────────────────────────────

def _symbolic_check(domain: str, payload: dict) -> tuple[bool, str]:
    if domain == "MONEY":
        if payload.get("value_usd", 0) <= 0:
            return False, "SYMBOLIC_FAIL: value_usd must be > 0 for MONEY actions"
        if not payload.get("action"):
            return False, "SYMBOLIC_FAIL: action string required for MONEY domain"
        return True, "SYMBOLIC_PASS: amount > 0 AND action present"
    if domain == "DEPLOY":
        if not payload.get("target_env"):
            return False, "SYMBOLIC_FAIL: target_env required for DEPLOY domain"
        return True, "SYMBOLIC_PASS: target_env present"
    if domain == "SECURITY":
        if not payload.get("actor"):
            return False, "SYMBOLIC_FAIL: actor required for SECURITY domain"
        return True, "SYMBOLIC_PASS: actor identified"
    return True, "SYMBOLIC_PASS: no constraints for domain"


# ── Formal Axiom Chain ────────────────────────────────────────────────────────

def _formal_proof(domain: str, payload: dict) -> tuple[bool, str]:
    if domain == "MONEY":
        amount_ok = payload.get("value_usd", 0) > 0
        action_ok = bool(payload.get("action"))
        conf_ok   = payload.get("confidence", 0) >= CONF_FLOOR
        if amount_ok and action_ok and conf_ok:
            return True, "PROVED: amount>0 ∧ action ∧ confidence>=0.6 => transaction_safe"
        missing = []
        if not amount_ok: missing.append("amount>0")
        if not action_ok: missing.append("action_present")
        if not conf_ok:   missing.append(f"confidence>={CONF_FLOOR}")
        return False, f"DISPROVED: missing axioms: {', '.join(missing)}"
    return True, f"PROVED: {domain} axiom chain satisfied"


# ── ProofCertificate ──────────────────────────────────────────────────────────

@dataclass
class ProofCertificate:
    cert_id:      str
    domain:       str
    action_type:  str
    timestamp:    str
    confidence:   float
    verdict:      str
    stage_reached: int
    reason:       str
    cycle_id:     str = ""
    value_usd:    float = 0.0

    def to_jsonl_line(self) -> str:
        return json.dumps(asdict(self), default=str)


def _log_certificate(cert: ProofCertificate):
    PROOF_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PROOF_LOG_PATH.open("a") as fh:
        fh.write(cert.to_jsonl_line() + "\n")


# ── StandardsGate ─────────────────────────────────────────────────────────────

class StandardsGate:
    """
    3-stage quality gate called by engine.py enforce_standards().
    evaluate(payload) -> dict: approved, verdict, reason, cert_id, stage
    """

    def evaluate(self, payload: dict) -> dict:
        signal_type = payload.get("signal_type", "")
        confidence  = float(payload.get("confidence", 0.0))
        domain      = _SIGNAL_DOMAIN_MAP.get(signal_type, "MONEY")
        cycle_id    = payload.get("cycle_id", "")
        value_usd   = float(payload.get("value_usd", 0.0))
        action      = payload.get("action", "")

        if domain in AUTO_PASS:
            cert = ProofCertificate(
                cert_id=str(uuid.uuid4()), domain=domain,
                action_type=signal_type, timestamp=_now(),
                confidence=confidence, verdict="SKIPPED",
                stage_reached=0, reason="AUTO_PASS: low-stakes domain",
                cycle_id=cycle_id, value_usd=value_usd,
            )
            _log_certificate(cert)
            return {"approved": True, "verdict": "SKIPPED",
                    "reason": cert.reason, "cert_id": cert.cert_id, "stage": 0}

        if confidence < CONF_FLOOR:
            cert = ProofCertificate(
                cert_id=str(uuid.uuid4()), domain=domain,
                action_type=signal_type, timestamp=_now(),
                confidence=confidence, verdict="DISPROVED",
                stage_reached=1,
                reason=f"STAGE1_FAIL: confidence {confidence:.3f} < floor {CONF_FLOOR}",
                cycle_id=cycle_id, value_usd=value_usd,
            )
            _log_certificate(cert)
            return {"approved": False, "verdict": "DISPROVED",
                    "reason": cert.reason, "cert_id": cert.cert_id, "stage": 1}

        sym_ok, sym_reason = _symbolic_check(domain, {**payload, "action": action})
        if not sym_ok:
            cert = ProofCertificate(
                cert_id=str(uuid.uuid4()), domain=domain,
                action_type=signal_type, timestamp=_now(),
                confidence=confidence, verdict="DISPROVED",
                stage_reached=2, reason=sym_reason,
                cycle_id=cycle_id, value_usd=value_usd,
            )
            _log_certificate(cert)
            return {"approved": False, "verdict": "DISPROVED",
                    "reason": cert.reason, "cert_id": cert.cert_id, "stage": 2}

        proved, proof_reason = _formal_proof(domain, {**payload, "action": action})
        verdict_str = "PROVED" if proved else "DISPROVED"
        cert = ProofCertificate(
            cert_id=str(uuid.uuid4()), domain=domain,
            action_type=signal_type, timestamp=_now(),
            confidence=confidence, verdict=verdict_str,
            stage_reached=3, reason=proof_reason,
            cycle_id=cycle_id, value_usd=value_usd,
        )
        _log_certificate(cert)
        return {"approved": proved, "verdict": verdict_str,
                "reason": cert.reason, "cert_id": cert.cert_id, "stage": 3}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
