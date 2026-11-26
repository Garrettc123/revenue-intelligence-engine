"""Regression coverage: internal standards are not human authorization."""
import unittest
from types import SimpleNamespace

from engine import RHNSRevenueEngine


class ExecutionSafetyTests(unittest.TestCase):
    def test_quality_approval_cannot_create_external_actions(self):
        engine = RHNSRevenueEngine.__new__(RHNSRevenueEngine)
        engine._notify_slack = lambda *_: self.fail("Unauthorized Slack notification")
        engine._add_hubspot_deal = lambda *_: self.fail("Unauthorized CRM write")
        outcome = engine.execute({"approved": True, "action": "PIPELINE_ADD"}, None)
        self.assertEqual(outcome["status"], "pending_approval")

    def test_quality_rejection_stays_blocked(self):
        engine = RHNSRevenueEngine.__new__(RHNSRevenueEngine)
        outcome = engine.execute({"approved": False, "reason": "low confidence"}, None)
        self.assertEqual(outcome["status"], "blocked")

    def test_run_cycle_does_not_forge_execution_receipt(self):
        engine = RHNSRevenueEngine.__new__(RHNSRevenueEngine)
        recorded = []
        engine.reason = lambda raw: {
            "signal_type": "opportunity", "confidence": 0.9, "urgency": "medium",
        }
        engine.harmonize = lambda signals: signals
        engine.navigate = lambda signal: "PIPELINE_ADD:proposal only"
        engine.enforce_standards = lambda action, signal, cycle_id: {
            "approved": True, "action": action, "cert_id": "gate-approved",
            "fingerprint": "gate-fp",
        }
        engine.record_outcome = lambda verdict, signal, outcome: recorded.append(outcome)
        engine.check_mastery = lambda confidence: None
        engine._notify_slack = lambda *_: self.fail("Unauthorized Slack notification")
        engine._add_hubspot_deal = lambda *_: self.fail("Unauthorized CRM write")

        verdict = engine.run_cycle({"source": "internal", "value_usd": 10})
        self.assertEqual(verdict["execution_status"], "pending_approval")
        self.assertEqual(recorded, ["pending_approval"])

    def test_mastery_candidate_cannot_emit_external_event(self):
        engine = RHNSRevenueEngine.__new__(RHNSRevenueEngine)
        stored = []
        engine.memory = SimpleNamespace(store_proof=lambda event: stored.append(event))
        engine.orchestrator = SimpleNamespace(emit_event=lambda event: self.fail(
            "Unauthorized mastery webhook"))
        engine.orchestrator_webhook = "https://example.invalid/operator"
        engine._emit_mastery_event()
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["event"], "SYSTEM_MASTERED")


if __name__ == "__main__":
    unittest.main()
