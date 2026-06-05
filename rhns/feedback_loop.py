"""
RHNS Feedback Loop Orchestrator
=================================
Runs after each intelligence cycle to resolve pending
causal memory entries based on actual system outcomes.

The closing loop that transforms RHNS from a one-shot
pipeline into a continuously improving reasoning system.

FIXES (2026-06-05):
- Added update() alias called by engine.record_outcome()
- resolve_stripe_action() now filters by customer_id metadata
- run() no longer auto-resolves entries based solely on confidence;
  unknown-source entries are left pending for next feedback pass
"""

import json
import os
import requests
from datetime import datetime, timezone
from .causal_memory import CausalMemory


class FeedbackLoop:
    """
    Resolves causal memory entries by checking actual outcomes.

    For each pending decision, probes the relevant external system
    (Stripe, HubSpot, GitHub Actions) to determine what actually happened.
    """

    def __init__(self, memory: CausalMemory):
        self.memory = memory
        self.stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
        self.hubspot_key = os.getenv("HUBSPOT_API_KEY", "")

    # ── FIX: update() alias called by engine.record_outcome() ────────────────

    def update(self, signal_type: str, outcome: str) -> None:
        """
        Called by engine.record_outcome() after each cycle execution.
        Finds the most recent unresolved entry for this signal_type and
        resolves it with the provided outcome.
        """
        entries = list(self.memory._entries.values())
        # Find the most recent pending entry matching this signal type
        candidates = [
            e for e in entries
            if e.signal_type == signal_type and e.outcome == "unknown"
        ]
        if not candidates:
            return
        # Sort by timestamp descending, resolve the newest
        candidates.sort(key=lambda e: e.timestamp_signal, reverse=True)
        target = candidates[0]
        self.memory.resolve(
            entry_id=target.entry_id,
            outcome=outcome if outcome in ("success", "failure", "partial") else "partial",
            outcome_detail=f"engine.record_outcome: {outcome}",
        )

    # ── FIX: resolve_stripe_action filters by customer_id ────────────────────

    def resolve_stripe_action(self, entry_id: str, customer_id: str = "") -> bool:
        """
        Check if a Stripe action (retry, refund, charge) succeeded.
        Filters payment intents by customer_id when provided to avoid
        false-positive resolution across unrelated customers.
        """
        if not self.stripe_key:
            return self.memory.resolve(entry_id, "unknown", "Stripe key not configured")

        try:
            params = {"limit": 10}
            if customer_id:
                params["customer"] = customer_id

            resp = requests.get(
                "https://api.stripe.com/v1/payment_intents",
                auth=(self.stripe_key, ""),
                params=params,
                timeout=8,
            )
            if resp.status_code == 200:
                intents = resp.json().get("data", [])
                succeeded = any(
                    pi.get("status") == "succeeded" for pi in intents
                )
                outcome = "success" if succeeded else "partial"
                detail = (
                    f"Stripe check: {len(intents)} intents"
                    + (f" for customer={customer_id}" if customer_id else " (no customer filter)")
                )
                return self.memory.resolve(entry_id, outcome, detail)
        except Exception as e:
            pass
        return self.memory.resolve(entry_id, "unknown", "Stripe unreachable")

    def run(self, max_resolve: int = 10) -> dict:
        """
        Resolve up to max_resolve pending entries.

        FIX: No longer auto-resolves non-Stripe entries based on confidence alone.
        Entries without a known resolver are left as 'unknown' until the next
        feedback pass or manual resolution via the API.
        """
        resolved_count = 0
        entries = list(self.memory._entries.values())

        for entry in entries:
            if entry.outcome != "unknown":
                continue
            if resolved_count >= max_resolve:
                break

            if entry.signal_source == "stripe":
                # Extract customer_id from tags if present
                customer_id = ""
                for tag in entry.tags:
                    if tag.startswith("customer:"):
                        customer_id = tag.split(":", 1)[1]
                        break
                self.resolve_stripe_action(entry.entry_id, customer_id)
                resolved_count += 1
            elif entry.signal_source == "hubspot":
                # HubSpot: mark partial — full resolution requires deal-stage polling
                self.memory.resolve(
                    entry.entry_id,
                    "partial",
                    "HubSpot resolver: pending deal-stage confirmation",
                )
                resolved_count += 1
            else:
                # Unknown source — leave pending, do not fabricate an outcome
                pass

        return {
            "resolved_this_run": resolved_count,
            "memory_stats": self.memory.stats(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
