"""
GARCAR REVENUE INTELLIGENCE ENGINE  v3.1
==========================================
Full-Stack End-to-End Platform Node

Architecture:
  ┌─────────────────────────────────────────────────────────┐
  │               GARCAR API BANK (shared)                  │
  │  Stripe · HubSpot · Shopify · Linear · Slack · Gumroad  │
  └──────────────────────┬──────────────────────┘
                         │
              ┌──────────┴──────────────┐
              │ MULTI-SOURCE SYNCHRONIZER  │   ← NEW v3.1
              │ window + dedup + boost     │
              └──────────┬──────────────┘
                         │
  ┌──────────────────────┬──────────────────────┐
  │            DAG ORCHESTRATOR  (autonomous-orchestrator)  │
  │  garcar_dag → dag_orchestrator → formal_verifier        │
  └──────────────────────┬──────────────────────┘
                         │
  ┌──────────────────────┬──────────────────────┐
  │                RHNS REASONING CORE                      │
  │  Reason → Harmonize → Navigate → Standards (quality)   │
  └──────────────────────┬──────────────────────┘
                         │
  ┌──────────────────────┬──────────────────────┐
  │           CAUSAL MEMORY + FEEDBACK LOOP                 │
  │  Every cycle reads + writes outcome proofs              │
  └───────────────────────────────────────────────────┘

Platform Standard: PLATFORM_STANDARD.md
Mastery Gate: confidence >= 0.85 on 50 consecutive cycles
              → emits SYSTEM_MASTERED event to orchestrator

v3.1 Changes:
- Bug fix: CausalMemory.store_proof() now exists (was crashing every cycle)
- Bug fix: FeedbackLoop.update() now exists (was crashing record_outcome)
- Bug fix: StandardsGate import unified to rhns.standards_gate (local)
- Bug fix: ProofCertificate now appended to proof_certificates.jsonl
- New: MultiSourceSynchronizer + run_synced_cycle() for multi-source autonomy
- New: confidence_override support in run_cycle() for sync-boosted signals
"""

import os
import json
import time
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, asdict, field

import requests

# ── RHNS local imports ─────────────────────────────────────────────────────
from rhns.causal_memory import CausalMemory
from rhns.feedback_loop import FeedbackLoop
from rhns.standards_gate import StandardsGate        # FIX: use local vendored gate
from rhns.multi_synchrony import MultiSourceSynchronizer

# ── Cross-repo: autonomous-orchestrator-core (vendored via pip / PYTHONPATH) ──
try:
    from core.dag_orchestrator import DAGOrchestrator
    from core.garcar_dag import GarcarDAG
    from core.formal_verifier import FormalVerifier
    from core.node_registry import NodeRegistry
    DAG_AVAILABLE = True
except ImportError:
    DAG_AVAILABLE = False
    print("[WARN] autonomous-orchestrator-core not on PYTHONPATH — DAG disabled.")

# ─────────────────────────────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────────────────────────────

@dataclass
class RevenueSignal:
    source: str
    signal_type: str   # opportunity|churn_risk|payment_failed|revenue_confirmed|upsell
    value_usd: float
    confidence: float  # 0.0 – 1.0
    action_required: str
    urgency: str       # immediate|high|medium|low
    timestamp: str
    metadata: dict = field(default_factory=dict)


@dataclass
class ProofCertificate:
    """Immutable execution receipt — written to CausalMemory and proof_certificates.jsonl."""
    cert_id: str
    cycle_id: str
    system_id: str = "revenue-intelligence-engine"
    signal_type: str = ""
    action: str = ""
    approved: bool = False
    value_usd: float = 0.0
    confidence: float = 0.0
    outcome: str = "pending"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    dag_node: str = "RIE_MAIN"
    standards_version: str = "1.1"

    def fingerprint(self) -> str:
        payload = f"{self.cert_id}:{self.signal_type}:{self.action}:{self.approved}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ─────────────────────────────────────────────────────────────────────────────────
# ENGINE
# ─────────────────────────────────────────────────────────────────────────────────

class RHNSRevenueEngine:
    """
    Full-stack RHNS Revenue Intelligence Engine v3.1.

    Lifecycle per cycle
    -------------------
    1. Ingest raw event data (single event or sync-collected batch)
    2. reason()        → typed RevenueSignal (respects confidence_override)
    3. harmonize()     → deduplicated, ranked signal list
    4. navigate()      → action string
    5. enforce_standards() → StandardsGate verdict + ProofCertificate
    6. execute()       → fire approved action (Stripe/HubSpot/Slack)
    7. record_outcome()→ write ProofCertificate to CausalMemory + JSONL
    8. feedback.run()  → resolve pending causal memory entries
    9. check_mastery() → emit SYSTEM_MASTERED if gate reached

    Multi-source path:
    ------------------
    run_synced_cycle() calls MultiSourceSynchronizer.collect() first,
    then runs each deduped+boosted event through run_cycle().
    """

    MASTERY_THRESHOLD = 0.85
    MASTERY_STREAK_REQUIRED = 50
    SYSTEM_ID = "revenue-intelligence-engine"

    def __init__(self):
        # ── API Bank keys (shared across all Garcar systems) ──────────────────
        self.stripe_key    = os.getenv('STRIPE_SECRET_KEY', '')
        self.hubspot_key   = os.getenv('HUBSPOT_API_KEY', '')
        self.slack_webhook = os.getenv('SLACK_WEBHOOK_URL', '')
        self.linear_key    = os.getenv('LINEAR_API_KEY', '')
        self.gumroad_key   = os.getenv('GUMROAD_ACCESS_TOKEN', '')
        self.shopify_token = os.getenv('SHOPIFY_ACCESS_TOKEN', '')
        self.shopify_store = os.getenv('SHOPIFY_STORE_DOMAIN', '')
        self.orchestrator_webhook = os.getenv('ORCHESTRATOR_WEBHOOK_URL', '')

        # ── RHNS core ─────────────────────────────────────────────────────
        self.signals: list[RevenueSignal] = []
        self.memory   = CausalMemory()
        self.feedback = FeedbackLoop(self.memory)
        self.gate     = StandardsGate()               # FIX: always use local gate
        self.sync     = MultiSourceSynchronizer()      # NEW: multi-source sync
        self.proofs:  list[ProofCertificate] = []

        # ── Mastery tracking ──────────────────────────────────────────────
        self._mastery_streak = 0
        self._mastered = False

        # ── DAG integration ───────────────────────────────────────────────
        if DAG_AVAILABLE:
            self.dag          = GarcarDAG()
            self.orchestrator = DAGOrchestrator(self.dag)
            self.verifier     = FormalVerifier()
            from core.node_registry import NodeRegistry
            self.registry     = NodeRegistry()
            self.registry.register(self.SYSTEM_ID, node_type="revenue", version="3.1")
            print(f"[INIT] DAG orchestrator online. Node: {self.SYSTEM_ID}")
        else:
            self.dag = self.orchestrator = self.verifier = self.registry = None

    # ── LAYER 1: REASON ───────────────────────────────────────────────

    def reason(self, data: dict) -> dict:
        """Extract first-principles signal from raw API event."""
        signal_type = 'opportunity'
        urgency     = 'medium'
        confidence  = 0.7

        ev = data.get('type', '')
        if ev == 'payment_intent.payment_failed':
            signal_type, urgency, confidence = 'payment_failed', 'immediate', 1.0
        elif ev == 'customer.subscription.deleted':
            signal_type, urgency, confidence = 'churn_risk', 'immediate', 0.95
        elif ev == 'payment_intent.succeeded':
            signal_type, urgency, confidence = 'revenue_confirmed', 'low', 1.0
        elif ev == 'invoice.upcoming':
            signal_type, urgency, confidence = 'upsell', 'high', 0.80
        elif ev == 'customer.subscription.updated':
            signal_type, urgency, confidence = 'opportunity', 'medium', 0.75

        # NEW: respect confidence_override from MultiSourceSynchronizer
        if 'confidence_override' in data:
            confidence = float(data['confidence_override'])
        else:
            # Apply causal memory adjustment only when not externally boosted
            memory_context = self.memory.format_for_reason_layer(signal_type)
            adjustment     = self.memory.confidence_adjustment(signal_type)
            confidence     = min(0.99, confidence * adjustment)

        memory_context = self.memory.format_for_reason_layer(signal_type)
        print(f"[REASON] {signal_type} | conf={confidence:.2f} | urgency={urgency}")
        return dict(signal_type=signal_type, urgency=urgency,
                    confidence=confidence, memory_context=memory_context)

    # ── LAYER 2: HARMONIZE ──────────────────────────────────────────────

    def harmonize(self, signals: list[RevenueSignal]) -> list[RevenueSignal]:
        """Deduplicate and rank across all sources."""
        urgency_rank = {'immediate': 0, 'high': 1, 'medium': 2, 'low': 3}
        seen, out = set(), []
        for s in sorted(signals, key=lambda x: urgency_rank.get(x.urgency, 4)):
            key = f"{s.source}:{s.signal_type}"
            if key not in seen:
                seen.add(key)
                out.append(s)
        return out

    # ── LAYER 3: NAVIGATE ───────────────────────────────────────────────

    def navigate(self, signal: RevenueSignal) -> str:
        """Determine optimal action path."""
        t, v = signal.signal_type, signal.value_usd
        multi = signal.metadata.get('source_count', 1)
        suffix = f" [x{multi} sources]" if multi > 1 else ""

        if t == 'payment_failed':
            return f"RETRY_PAYMENT:Contact {signal.metadata.get('customer','unknown')} <2h. ${v:.2f}{suffix}"
        if t == 'churn_risk':
            return f"RETENTION_SEQUENCE:Win-back ${v:.2f}/mo at-risk revenue{suffix}"
        if t == 'revenue_confirmed':
            return f"LOG_REVENUE:Record ${v:.2f} confirmed. Trigger upsell check.{suffix}"
        if t == 'upsell':
            return f"UPSELL_TRIGGER:Present upgrade. +${v:.2f}{suffix}"
        if t == 'opportunity':
            return f"PIPELINE_ADD:HubSpot deal stage. Est. ${v:.2f}{suffix}"
        return "MONITOR:Track 24h"

    # ── LAYER 4: STANDARDS GATE ─────────────────────────────────────────────

    def enforce_standards(self, action: str, signal: RevenueSignal,
                          cycle_id: str = "") -> dict:
        """Quality gate — blocks execution if confidence < 0.6 or gate rejects."""
        dag_verdict = self.gate.evaluate({
            "action": action,
            "signal_type": signal.signal_type,
            "confidence": signal.confidence,
            "value_usd": signal.value_usd,
            "cycle_id": cycle_id,
        })
        approved = dag_verdict.get("approved", False)
        reason   = dag_verdict.get("reason", "")

        cert = ProofCertificate(
            cert_id=str(uuid.uuid4()),
            cycle_id=cycle_id,
            signal_type=signal.signal_type,
            action=action,
            approved=approved,
            value_usd=signal.value_usd,
            confidence=signal.confidence,
        )
        self.proofs.append(cert)
        # FIX: store_proof now exists and appends to proof_certificates.jsonl
        self.memory.store_proof(asdict(cert))

        verdict = dict(action=action, approved=approved, reason=reason,
                       cert_id=cert.cert_id, fingerprint=cert.fingerprint())
        print(f"[STANDARDS] {verdict}")
        return verdict

    # ── EXECUTION ───────────────────────────────────────────────────────────────────

    def _notify_slack(self, msg: str):
        if not self.slack_webhook:
            return
        try:
            requests.post(self.slack_webhook,
                          json={"text": f"[RIE] {msg}"}, timeout=5)
        except Exception as e:
            print(f"[SLACK ERR] {e}")

    def _add_hubspot_deal(self, signal: RevenueSignal):
        if not self.hubspot_key:
            return
        url = "https://api.hubapi.com/crm/v3/objects/deals"
        payload = {"properties": {
            "dealname": f"RIE Opportunity {signal.timestamp[:10]}",
            "amount": str(signal.value_usd),
            "dealstage": "appointmentscheduled",
            "pipeline": "default",
        }}
        try:
            r = requests.post(url, json=payload,
                              headers={"Authorization": f"Bearer {self.hubspot_key}"},
                              timeout=8)
            print(f"[HUBSPOT] Deal created: {r.status_code}")
        except Exception as e:
            print(f"[HUBSPOT ERR] {e}")

    def execute(self, verdict: dict, signal: RevenueSignal):
        """Fire the approved action."""
        if not verdict['approved']:
            print(f"[EXEC] Blocked — {verdict['reason']}")
            return
        action = verdict['action']
        print(f"[EXEC] Firing: {action}")
        self._notify_slack(action)
        if "PIPELINE_ADD" in action or "UPSELL_TRIGGER" in action:
            self._add_hubspot_deal(signal)

    # ── OUTCOME + MASTERY ──────────────────────────────────────────────────

    def record_outcome(self, verdict: dict, signal: RevenueSignal,
                       outcome: str = "executed"):
        # FIX: feedback.update() now exists
        self.feedback.update(signal.signal_type, outcome)
        for cert in self.proofs:
            if cert.cert_id == verdict.get('cert_id'):
                cert.outcome = outcome
                self.memory.store_proof(asdict(cert))

    def check_mastery(self, cycle_conf: float):
        if self._mastered:
            return
        if cycle_conf >= self.MASTERY_THRESHOLD:
            self._mastery_streak += 1
        else:
            self._mastery_streak = 0
        if self._mastery_streak >= self.MASTERY_STREAK_REQUIRED:
            self._mastered = True
            print(f"[MASTERY] {self.SYSTEM_ID} MASTERED after "
                  f"{self.MASTERY_STREAK_REQUIRED} consecutive high-confidence cycles.")
            self._emit_mastery_event()

    def _emit_mastery_event(self):
        event = {
            "event": "SYSTEM_MASTERED",
            "system_id": self.SYSTEM_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mastery_threshold": self.MASTERY_THRESHOLD,
            "streak": self.MASTERY_STREAK_REQUIRED,
        }
        self.memory.store_proof(event)
        if DAG_AVAILABLE and self.orchestrator:
            self.orchestrator.emit_event(event)
        if self.orchestrator_webhook:
            try:
                requests.post(self.orchestrator_webhook, json=event, timeout=5)
            except Exception as e:
                print(f"[MASTERY EMIT ERR] {e}")

    # ── MAIN CYCLE ───────────────────────────────────────────────────────────────────

    def run_cycle(self, raw_event: dict) -> dict:
        """
        Full RHNS → Standards → execute cycle.
        Returns the final verdict dict.
        """
        cycle_id = str(uuid.uuid4())
        print(f"\n{'='*60}")
        print(f"[CYCLE] {cycle_id}  |  {datetime.now(timezone.utc).isoformat()}")
        print(f"{'='*60}")

        # 1. Reason
        reasoned = self.reason(raw_event)

        # 2. Build RevenueSignal
        signal = RevenueSignal(
            source=raw_event.get('source', 'stripe'),
            signal_type=reasoned['signal_type'],
            value_usd=float(raw_event.get('value_usd', 0)),
            confidence=reasoned['confidence'],
            action_required='',
            urgency=reasoned['urgency'],
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=raw_event.get('metadata', {}),
        )

        # 3. Harmonize
        [signal] = self.harmonize([signal])

        # 4. Navigate
        action = self.navigate(signal)
        signal.action_required = action

        # 5. Standards gate
        verdict = self.enforce_standards(action, signal, cycle_id)

        # 6. Execute
        self.execute(verdict, signal)

        # 7. Record outcome + mastery
        outcome = 'executed' if verdict['approved'] else 'blocked'
        self.record_outcome(verdict, signal, outcome)
        self.check_mastery(signal.confidence)

        print(f"[CYCLE DONE] cert={verdict.get('cert_id')} "
              f"fp={verdict.get('fingerprint')} outcome={outcome}")
        return verdict

    def run_batch(self, events: list[dict]) -> list[dict]:
        """Process a batch of raw events through the full cycle."""
        return [self.run_cycle(e) for e in events]

    # ── MULTI-SOURCE SYNCED CYCLE ───────────────────────────────────────────────

    def run_synced_cycle(self) -> dict:
        """
        Full autonomous multi-source cycle:
        1. MultiSourceSynchronizer polls all configured API sources
        2. Signals are windowed, deduplicated, and confidence-boosted
        3. Each deduped signal runs through the full RHNS pipeline
        4. FeedbackLoop.run() resolves pending causal memory entries
        5. Returns aggregated summary

        This is the autonomous entrypoint — call on a schedule (cron/APScheduler)
        with no external input required.
        """
        started_at = datetime.now(timezone.utc).isoformat()
        print(f"\n{'#'*60}")
        print(f"[SYNCED CYCLE] {started_at}")
        print(f"{'#'*60}")

        # Step 1: collect from all sources
        sync_events = self.sync.collect()
        print(f"[SYNCED CYCLE] {len(sync_events)} events after sync deduplication")

        if not sync_events:
            print("[SYNCED CYCLE] No events — running feedback loop only")
            feedback_result = self.feedback.run(max_resolve=20)
            return {
                "synced": True,
                "events_processed": 0,
                "verdicts": [],
                "feedback": feedback_result,
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }

        # Step 2: run each event through the full cycle
        verdicts = []
        for ev in sync_events:
            try:
                verdict = self.run_cycle(ev)
                verdicts.append(verdict)
            except Exception as e:
                print(f"[SYNCED CYCLE] cycle error for event: {e}")
                verdicts.append({"error": str(e), "event": ev.get("type", "?")})

        # Step 3: resolve pending causal memory entries
        feedback_result = self.feedback.run(max_resolve=20)

        summary = {
            "synced": True,
            "sync_sources": self.sync.status(),
            "events_processed": len(verdicts),
            "approved": sum(1 for v in verdicts if v.get("approved")),
            "blocked": sum(1 for v in verdicts if not v.get("approved") and "error" not in v),
            "errors": sum(1 for v in verdicts if "error" in v),
            "mastered": self._mastered,
            "mastery_streak": self._mastery_streak,
            "feedback": feedback_result,
            "verdicts": verdicts,
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        print(f"[SYNCED CYCLE DONE] approved={summary['approved']} "
              f"blocked={summary['blocked']} errors={summary['errors']}")
        return summary


# ── ENTRYPOINT ─────────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    engine = RHNSRevenueEngine()

    import sys
    if '--sync' in sys.argv:
        # Run full autonomous multi-source cycle
        result = engine.run_synced_cycle()
    else:
        # Single test event
        test_event = {
            'type': 'payment_intent.payment_failed',
            'source': 'stripe',
            'value_usd': 299.0,
            'metadata': {'customer': 'cus_test123'},
        }
        result = engine.run_cycle(test_event)

    print(json.dumps(result, indent=2, default=str))
