"""
RHNS Causal Memory — Feedback Loop Engine
==========================================
Stores (signal, action, outcome) tuples and provides
pattern retrieval for the Reason layer.

Inspired by: LOOP architecture (LLM↔planner + causal memory),
SagaLLM transactional patterns, and AgentNet DAG coordination.
"""

import json
import os
import time
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from typing import Optional
from pathlib import Path

PROOF_LOG_PATH = Path("rhns/proof_certificates.jsonl")


@dataclass
class CausalEntry:
    """One (signal → action → outcome) causal memory tuple."""
    entry_id: str = ""
    signal_type: str = ""
    signal_source: str = ""
    action_taken: str = ""
    action_approved: bool = False
    outcome: str = ""           # success | failure | partial | unknown
    outcome_detail: str = ""
    value_usd: float = 0.0
    confidence_at_decision: float = 0.0
    confidence_updated: float = 0.0   # adjusted after outcome
    timestamp_signal: str = ""
    timestamp_action: str = ""
    timestamp_outcome: str = ""
    cycle_id: str = ""
    tags: list = field(default_factory=list)


class CausalMemory:
    """
    Persistent causal memory for the RHNS pipeline.

    Stores decisions and their outcomes in a JSON file.
    Provides pattern retrieval so the Reason layer can
    consult history before making new decisions.

    Key capabilities:
    - record(): Log a new (signal → action) decision
    - resolve(): Update an entry with its actual outcome
    - recall(): Retrieve relevant past patterns for a given signal type
    - confidence_adjustment(): Compute updated confidence based on outcome history
    - stats(): Return aggregate performance metrics
    - store_proof(): Append a ProofCertificate dict to proof_certificates.jsonl
    """

    def __init__(self, path: str = "rhns/causal_memory.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, CausalEntry] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text())
                self._entries = {k: CausalEntry(**v) for k, v in raw.items()}
            except Exception:
                self._entries = {}

    def _save(self):
        data = {k: asdict(v) for k, v in self._entries.items()}
        self.path.write_text(json.dumps(data, indent=2))

    def _make_id(self, signal_type: str, timestamp: str) -> str:
        raw = f"{signal_type}:{timestamp}:{time.time()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def record(
        self,
        signal_type: str,
        signal_source: str,
        action_taken: str,
        action_approved: bool,
        value_usd: float = 0.0,
        confidence: float = 0.0,
        cycle_id: str = "",
        tags: list = None,
    ) -> str:
        """Record a new decision. Returns the entry_id for later resolution."""
        now = datetime.now(timezone.utc).isoformat()
        entry_id = self._make_id(signal_type, now)

        entry = CausalEntry(
            entry_id=entry_id,
            signal_type=signal_type,
            signal_source=signal_source,
            action_taken=action_taken,
            action_approved=action_approved,
            outcome="unknown",
            value_usd=value_usd,
            confidence_at_decision=confidence,
            confidence_updated=confidence,
            timestamp_signal=now,
            timestamp_action=now,
            cycle_id=cycle_id,
            tags=tags or [],
        )
        self._entries[entry_id] = entry
        self._save()
        return entry_id

    def resolve(
        self,
        entry_id: str,
        outcome: str,
        outcome_detail: str = "",
        actual_value_usd: float = None,
    ) -> bool:
        """Update an entry with its actual outcome. Returns True if found."""
        if entry_id not in self._entries:
            return False

        entry = self._entries[entry_id]
        entry.outcome = outcome
        entry.outcome_detail = outcome_detail
        entry.timestamp_outcome = datetime.now(timezone.utc).isoformat()

        if actual_value_usd is not None:
            entry.value_usd = actual_value_usd

        # Bayesian confidence update
        outcome_multipliers = {
            "success": 1.15,
            "partial": 1.0,
            "failure": 0.7,
            "unknown": 1.0,
        }
        multiplier = outcome_multipliers.get(outcome, 1.0)
        entry.confidence_updated = min(0.99, entry.confidence_at_decision * multiplier)

        self._entries[entry_id] = entry
        self._save()
        return True

    def recall(
        self,
        signal_type: str,
        limit: int = 5,
        min_confidence: float = 0.0,
    ) -> list[CausalEntry]:
        """
        Retrieve relevant past patterns for a signal type.
        Returns most recent resolved entries, sorted by updated confidence.
        Used by the Reason layer before making new decisions.
        """
        matches = [
            e for e in self._entries.values()
            if e.signal_type == signal_type
            and e.outcome != "unknown"
            and e.confidence_updated >= min_confidence
        ]
        return sorted(matches, key=lambda x: x.confidence_updated, reverse=True)[:limit]

    def confidence_adjustment(self, signal_type: str) -> float:
        """
        Compute a confidence modifier for a signal type based on outcome history.
        Returns a multiplier (e.g., 0.8 means reduce base confidence by 20%).
        """
        history = self.recall(signal_type, limit=20)
        if not history:
            return 1.0  # No history — use base confidence

        outcomes = [e.outcome for e in history]
        success_rate = outcomes.count("success") / len(outcomes)
        failure_rate = outcomes.count("failure") / len(outcomes)

        if success_rate > 0.7:
            return 1.2
        elif failure_rate > 0.5:
            return 0.6
        else:
            return 1.0

    def stats(self) -> dict:
        """Return aggregate memory stats."""
        entries = list(self._entries.values())
        resolved = [e for e in entries if e.outcome != "unknown"]

        return {
            "total_entries": len(entries),
            "resolved": len(resolved),
            "pending_resolution": len(entries) - len(resolved),
            "success_rate": (
                sum(1 for e in resolved if e.outcome == "success") / len(resolved)
                if resolved else 0.0
            ),
            "failure_rate": (
                sum(1 for e in resolved if e.outcome == "failure") / len(resolved)
                if resolved else 0.0
            ),
            "total_value_tracked_usd": sum(e.value_usd for e in entries),
            "signal_types": list(set(e.signal_type for e in entries)),
        }

    def format_for_reason_layer(self, signal_type: str) -> str:
        """
        Format causal memory context for injection into the Reason layer prompt.
        Returns a concise summary of past outcomes for this signal type.
        """
        history = self.recall(signal_type, limit=3)
        if not history:
            return f"No prior memory for signal_type='{signal_type}'."

        lines = [f"Causal memory for '{signal_type}' ({len(history)} entries):"]
        for e in history:
            lines.append(
                f"  [{e.outcome.upper()}] action='{e.action_taken[:60]}' "
                f"confidence={e.confidence_updated:.2f} value=${e.value_usd:.2f}"
            )
        return "\n".join(lines)

    # ── FIX: store_proof — appends ProofCertificate dicts to JSONL log ────────

    def store_proof(self, proof: dict) -> None:
        """
        Append a ProofCertificate (or any dict) to proof_certificates.jsonl.
        Also records a lightweight CausalEntry if signal_type is present.
        """
        PROOF_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(proof, default=str)
        with PROOF_LOG_PATH.open("a") as fh:
            fh.write(line + "\n")

        # Mirror into causal memory if it looks like a full cycle proof
        signal_type = proof.get("signal_type", "")
        if signal_type and proof.get("cert_id"):
            self.record(
                signal_type=signal_type,
                signal_source=proof.get("dag_node", "engine"),
                action_taken=proof.get("action", ""),
                action_approved=proof.get("approved", False),
                value_usd=float(proof.get("value_usd", 0.0)),
                confidence=float(proof.get("confidence", 0.0)),
                cycle_id=proof.get("cycle_id", ""),
                tags=["proof_certificate"],
            )
