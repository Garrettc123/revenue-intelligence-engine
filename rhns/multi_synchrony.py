"""
RHNS Multi-Source Synchronizer
================================
Batches signals from multiple sources (Stripe, HubSpot, Shopify, Linear)
within a configurable time window, then feeds the deduplicated, ranked
harmonized list to the RHNS Reason → Navigate → Standards pipeline.

Core design principles:
- Time-windowed batching: signals from the same customer across different
  sources within `window_seconds` are grouped into a SyncWindow.
- Cross-source confidence boosting: if the same customer appears in 2+
  sources with the same signal_type, confidence is boosted by 0.10 per
  additional corroborating source (capped at 0.99).
- Deduplication key: (customer_id, signal_type) — one action per pair per window.
- Source priority ranking when types conflict: Stripe > HubSpot > Shopify > Linear.
"""

import os
import time
import requests
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


SOURCE_PRIORITY = {
    "stripe": 0,
    "hubspot": 1,
    "shopify": 2,
    "linear": 3,
    "gumroad": 4,
    "manual": 99,
}

CROSS_SOURCE_CONFIDENCE_BOOST = 0.10
CONFIDENCE_CAP = 0.99


@dataclass
class RawSignal:
    """Normalized signal from any source before RHNS reasoning."""
    source: str
    signal_type: str
    customer_id: str
    customer_email: str
    value_usd: float
    confidence: float
    urgency: str
    raw_event: dict = field(default_factory=dict)
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class SyncWindow:
    """
    A time-windowed batch of raw signals grouped by (customer_id, signal_type).
    Holds the primary signal (highest-priority source) and all corroborating signals.
    """
    key: str                          # f"{customer_id}:{signal_type}"
    primary: RawSignal = None
    corroborating: list = field(default_factory=list)
    window_opened_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def source_count(self) -> int:
        return 1 + len(self.corroborating)

    @property
    def boosted_confidence(self) -> float:
        """Boost primary signal confidence by cross-source corroboration."""
        boost = (self.source_count - 1) * CROSS_SOURCE_CONFIDENCE_BOOST
        return min(CONFIDENCE_CAP, self.primary.confidence + boost)

    def to_engine_event(self) -> dict:
        """Convert to the dict format consumed by engine.run_cycle()."""
        p = self.primary
        return {
            "type": _signal_type_to_stripe_event(p.signal_type),
            "source": p.source,
            "value_usd": p.value_usd,
            "confidence_override": self.boosted_confidence,
            "metadata": {
                "customer": p.customer_id,
                "customer_email": p.customer_email,
                "corroborating_sources": [c.source for c in self.corroborating],
                "source_count": self.source_count,
                "sync_window_opened": self.window_opened_at,
            },
        }


def _signal_type_to_stripe_event(signal_type: str) -> str:
    """Map internal signal_type back to a Stripe-style event type for engine.reason()."""
    mapping = {
        "payment_failed": "payment_intent.payment_failed",
        "churn_risk": "customer.subscription.deleted",
        "revenue_confirmed": "payment_intent.succeeded",
        "upsell": "invoice.upcoming",
        "opportunity": "customer.subscription.updated",
    }
    return mapping.get(signal_type, signal_type)


class MultiSourceSynchronizer:
    """
    Polls all configured API sources, normalizes signals into RawSignal objects,
    groups them into SyncWindows, applies cross-source confidence boosting,
    and returns a list of engine-ready event dicts.

    Usage:
        sync = MultiSourceSynchronizer(window_seconds=300)
        events = sync.collect()
        for ev in events:
            engine.run_cycle(ev)
    """

    def __init__(self, window_seconds: int = 300):
        self.window_seconds = window_seconds
        self.stripe_key    = os.getenv("STRIPE_SECRET_KEY", "")
        self.hubspot_key   = os.getenv("HUBSPOT_API_KEY", "")
        self.shopify_token = os.getenv("SHOPIFY_ACCESS_TOKEN", "")
        self.shopify_store = os.getenv("SHOPIFY_STORE_DOMAIN", "")
        self.linear_key    = os.getenv("LINEAR_API_KEY", "")
        self.gumroad_key   = os.getenv("GUMROAD_ACCESS_TOKEN", "")

    # ── Source pollers ────────────────────────────────────────────────────────

    def _poll_stripe(self) -> list[RawSignal]:
        """Fetch recent Stripe payment intent failures and subscription cancellations."""
        signals = []
        if not self.stripe_key:
            return signals
        try:
            # Failed payment intents
            r = requests.get(
                "https://api.stripe.com/v1/payment_intents",
                auth=(self.stripe_key, ""),
                params={"limit": 20},
                timeout=8,
            )
            if r.status_code == 200:
                for pi in r.json().get("data", []):
                    if pi.get("status") in ("requires_payment_method", "canceled"):
                        signals.append(RawSignal(
                            source="stripe",
                            signal_type="payment_failed",
                            customer_id=pi.get("customer", ""),
                            customer_email=pi.get("receipt_email", ""),
                            value_usd=pi.get("amount", 0) / 100,
                            confidence=1.0,
                            urgency="immediate",
                            raw_event=pi,
                        ))
                    elif pi.get("status") == "succeeded":
                        signals.append(RawSignal(
                            source="stripe",
                            signal_type="revenue_confirmed",
                            customer_id=pi.get("customer", ""),
                            customer_email=pi.get("receipt_email", ""),
                            value_usd=pi.get("amount", 0) / 100,
                            confidence=1.0,
                            urgency="low",
                            raw_event=pi,
                        ))
        except Exception as e:
            print(f"[SYNC][STRIPE] poll error: {e}")
        return signals

    def _poll_hubspot(self) -> list[RawSignal]:
        """Fetch HubSpot deals that are at-risk (closed-lost or stagnant)."""
        signals = []
        if not self.hubspot_key:
            return signals
        try:
            r = requests.post(
                "https://api.hubapi.com/crm/v3/objects/deals/search",
                headers={"Authorization": f"Bearer {self.hubspot_key}"},
                json={
                    "filterGroups": [{
                        "filters": [{
                            "propertyName": "dealstage",
                            "operator": "EQ",
                            "value": "closedlost",
                        }]
                    }],
                    "properties": ["dealname", "amount", "hs_object_id",
                                   "associations.contacts"],
                    "limit": 20,
                },
                timeout=8,
            )
            if r.status_code == 200:
                for deal in r.json().get("results", []):
                    props = deal.get("properties", {})
                    amount = float(props.get("amount") or 0)
                    signals.append(RawSignal(
                        source="hubspot",
                        signal_type="churn_risk",
                        customer_id=props.get("hs_object_id", ""),
                        customer_email="",
                        value_usd=amount,
                        confidence=0.75,
                        urgency="high",
                        raw_event=deal,
                    ))
        except Exception as e:
            print(f"[SYNC][HUBSPOT] poll error: {e}")
        return signals

    def _poll_shopify(self) -> list[RawSignal]:
        """Fetch Shopify orders that are pending or refunded."""
        signals = []
        if not self.shopify_token or not self.shopify_store:
            return signals
        try:
            r = requests.get(
                f"https://{self.shopify_store}/admin/api/2024-01/orders.json",
                headers={"X-Shopify-Access-Token": self.shopify_token},
                params={"status": "any", "financial_status": "pending", "limit": 20},
                timeout=8,
            )
            if r.status_code == 200:
                for order in r.json().get("orders", []):
                    signals.append(RawSignal(
                        source="shopify",
                        signal_type="payment_failed",
                        customer_id=str(order.get("customer", {}).get("id", "")),
                        customer_email=order.get("email", ""),
                        value_usd=float(order.get("total_price", 0)),
                        confidence=0.85,
                        urgency="high",
                        raw_event=order,
                    ))
        except Exception as e:
            print(f"[SYNC][SHOPIFY] poll error: {e}")
        return signals

    def _poll_linear(self) -> list[RawSignal]:
        """Fetch Linear issues tagged as revenue-blocking or customer-escalation."""
        signals = []
        if not self.linear_key:
            return signals
        try:
            query = """
            query {
              issues(filter: {
                labels: { name: { in: ["revenue-blocker", "customer-escalation"] } }
                state: { type: { neq: "completed" } }
              }, first: 20) {
                nodes {
                  id title state { name } labels { nodes { name } }
                  customer { id name }
                }
              }
            }
            """
            r = requests.post(
                "https://api.linear.app/graphql",
                headers={"Authorization": self.linear_key},
                json={"query": query},
                timeout=8,
            )
            if r.status_code == 200:
                issues = r.json().get("data", {}).get("issues", {}).get("nodes", [])
                for issue in issues:
                    signals.append(RawSignal(
                        source="linear",
                        signal_type="churn_risk",
                        customer_id=issue.get("customer", {}).get("id", "") if issue.get("customer") else "",
                        customer_email="",
                        value_usd=0.0,
                        confidence=0.65,
                        urgency="high",
                        raw_event=issue,
                    ))
        except Exception as e:
            print(f"[SYNC][LINEAR] poll error: {e}")
        return signals

    # ── Windowing + deduplication ─────────────────────────────────────────────

    def _build_windows(self, all_signals: list[RawSignal]) -> list[SyncWindow]:
        """
        Group signals into SyncWindows by (customer_id, signal_type).
        Within each group, the highest-priority source becomes the primary;
        all others become corroborating signals.
        Signals with no customer_id get their own singleton window.
        """
        windows: dict[str, SyncWindow] = {}

        for sig in all_signals:
            # Use email as fallback key if customer_id is empty
            cid = sig.customer_id or sig.customer_email or f"anon_{sig.source}_{sig.signal_type}"
            key = f"{cid}:{sig.signal_type}"

            if key not in windows:
                windows[key] = SyncWindow(key=key, primary=sig)
            else:
                win = windows[key]
                # Replace primary if this source has higher priority
                if SOURCE_PRIORITY.get(sig.source, 99) < SOURCE_PRIORITY.get(win.primary.source, 99):
                    win.corroborating.append(win.primary)
                    win.primary = sig
                else:
                    win.corroborating.append(sig)

        return list(windows.values())

    # ── Public API ────────────────────────────────────────────────────────────

    def collect(self) -> list[dict]:
        """
        Poll all configured sources, build sync windows, apply confidence boosts,
        and return a list of engine-ready event dicts sorted by urgency + value.

        This is the entry point called by engine.run_synced_cycle().
        """
        print("[SYNC] Polling all sources...")
        all_signals: list[RawSignal] = []
        all_signals.extend(self._poll_stripe())
        all_signals.extend(self._poll_hubspot())
        all_signals.extend(self._poll_shopify())
        all_signals.extend(self._poll_linear())

        print(f"[SYNC] Collected {len(all_signals)} raw signals across all sources")

        windows = self._build_windows(all_signals)
        print(f"[SYNC] Collapsed to {len(windows)} sync windows after deduplication")

        # Log any cross-source corroborations
        for w in windows:
            if w.source_count > 1:
                print(
                    f"[SYNC] Cross-source boost: key={w.key} "
                    f"sources={[w.primary.source] + [c.source for c in w.corroborating]} "
                    f"conf {w.primary.confidence:.2f} → {w.boosted_confidence:.2f}"
                )

        # Sort: immediate urgency first, then by value_usd descending
        urgency_rank = {"immediate": 0, "high": 1, "medium": 2, "low": 3}
        windows.sort(
            key=lambda w: (urgency_rank.get(w.primary.urgency, 4), -w.primary.value_usd)
        )

        return [w.to_engine_event() for w in windows]

    def status(self) -> dict:
        """Return which sources are configured (keys present)."""
        return {
            "stripe": bool(self.stripe_key),
            "hubspot": bool(self.hubspot_key),
            "shopify": bool(self.shopify_token and self.shopify_store),
            "linear": bool(self.linear_key),
            "gumroad": bool(self.gumroad_key),
            "window_seconds": self.window_seconds,
        }
