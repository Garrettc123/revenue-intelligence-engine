# GARCAR Revenue Intelligence Engine

> Autonomous RHNS-powered revenue monitoring and decision system

## Overview

The **GARCAR Revenue Intelligence Engine** is an autonomous Python-based system that monitors all revenue streams, predicts churn, identifies upsell opportunities, and fires close actions across Stripe, HubSpot, Shopify, and Linear — powered by the RHNS decision framework.

## RHNS Framework

Every revenue signal passes through four cognitive layers:

| Layer | Role | Description |
|-------|------|-------------|
| **R**eason | Signal Extraction | Analyzes raw event data and classifies signal type, urgency, and confidence |
| **H**armony | Cross-source Alignment | Deduplicates and ranks signals across all revenue sources by urgency and value |
| **N**avigation | Action Routing | Determines the optimal autonomous action for each signal |
| **S**tandards | Quality Gate | Enforces confidence thresholds before any action fires |

## Revenue Streams Monitored

- **Stripe** — Payment intents, subscription events, failed payments
- **HubSpot** — Deal pipeline stages, open opportunities
- **Shopify** — Order events *(extensible)*
- **Gumroad** — Digital product sales *(extensible)*
- **Linear** — Billing and contract issues *(extensible)*

## Signal Types

| Signal | Urgency | Autonomous Action |
|--------|---------|-------------------|
| `payment_failed` | Immediate | Retry + customer contact within 2h |
| `churn_risk` | Immediate | Win-back retention sequence |
| `opportunity` | High | Add to HubSpot pipeline |
| `upsell` | Medium | Present upgrade offer |
| `revenue_confirmed` | Low | Log to Notion revenue ledger |
| `heartbeat` | Low | System health confirmation |

## Architecture

```
engine.py
├── RHNSRevenueEngine          # Core decision engine
│   ├── reason()               # Layer 1: Signal classification
│   ├── harmonize()            # Layer 2: Cross-source dedup + ranking
│   ├── navigate()             # Layer 3: Action determination
│   ├── enforce_standards()    # Layer 4: Confidence quality gate
│   ├── check_stripe()         # Stripe poller
│   ├── check_hubspot_pipeline() # HubSpot poller
│   ├── broadcast()            # Slack alert dispatcher
│   └── run_cycle()            # Orchestrates one full RHNS cycle
└── RevenueSignal              # Typed signal dataclass
```

## GitHub Actions

The workflow runs **every hour** automatically:

```
.github/workflows/revenue-intelligence.yml
```

- Polls all connected revenue sources
- Runs the full RHNS decision cycle
- Commits output JSON to `output/` directory
- Uploads artifacts for 30-day retention
- Broadcasts high-urgency signals to Slack

## Setup

### 1. Configure Repository Secrets

Go to **Settings → Secrets and variables → Actions** and add:

| Secret | Required | Description |
|--------|----------|-------------|
| `STRIPE_SECRET_KEY` | Recommended | Stripe secret key (`sk_live_...`) |
| `HUBSPOT_API_KEY` | Optional | HubSpot private app token |
| `DEFENDER_SLACK_WEBHOOK` | Optional | Slack incoming webhook URL |
| `LINEAR_API_KEY` | Optional | Linear API key |

### 2. Run Manually

Trigger a cycle on-demand via **Actions → RHNS Revenue Intelligence Cycle → Run workflow**.

### 3. Local Development

```bash
pip install -r requirements.txt

export STRIPE_SECRET_KEY=sk_test_...
export HUBSPOT_API_KEY=pat-...
export SLACK_WEBHOOK_URL=https://hooks.slack.com/...

python engine.py
```

## Output

Each cycle writes a JSON file to `output/cycle-{timestamp}.json`:

```json
{
  "cycle_time": "2025-01-15T14:00:00Z",
  "signals_processed": 3,
  "actions_approved": 2,
  "results": [
    {
      "action": "RETRY_PAYMENT: Contact customer@example.com within 2h. Value: $299.00",
      "approved": true,
      "reason": "Confidence threshold met",
      "signal": { ... }
    }
  ]
}
```

## Extending

To add a new revenue source (e.g. Shopify), add a method:

```python
def check_shopify(self) -> list[RevenueSignal]:
    # Poll Shopify Orders API
    # Return list of RevenueSignal objects
    ...
```

Then call it in `run_cycle()`:

```python
raw_signals.extend(self.check_shopify())
```

---

*Built with the RHNS framework — Reason, Harmony, Navigation, Standards.*
