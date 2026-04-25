# GARCAR PLATFORM STANDARD v1.0

> **Every one of the 332 Garcar systems inherits this contract.**
> Update this file at the root and all systems absorb it on next deploy.

---

## 1. Identity

Every system MUST declare:

```python
SYSTEM_ID      = "<repo-name>"         # matches GitHub repo slug
SYSTEM_VERSION = "<semver>"            # e.g. "3.0.0"
PLATFORM_STD   = "GARCAR-STD-1.0"
```

---

## 2. Shared API Bank

All secrets are loaded from environment variables — never hardcoded.

| Key | Service |
|---|---|
| `STRIPE_SECRET_KEY` | Stripe payments |
| `HUBSPOT_API_KEY` | HubSpot CRM |
| `SHOPIFY_ACCESS_TOKEN` | Shopify commerce |
| `SHOPIFY_STORE_DOMAIN` | Shopify store URL |
| `LINEAR_API_KEY` | Linear project management |
| `SLACK_WEBHOOK_URL` | Slack notifications |
| `GUMROAD_ACCESS_TOKEN` | Gumroad digital sales |
| `ORCHESTRATOR_WEBHOOK_URL` | Master orchestrator event bus |
| `OPENAI_API_KEY` | GPT inference |
| `ANTHROPIC_API_KEY` | Claude inference |
| `NOTION_API_KEY` | Notion data store |
| `ZAPIER_WEBHOOK_URL` | Zapier automation bridge |
| `AWS_ACCESS_KEY_ID` | AWS S3 / IAM |
| `AWS_SECRET_ACCESS_KEY` | AWS S3 / IAM |

---

## 3. RHNS Architecture (mandatory layers)

Every system runs four layers in order:

```
Reason → Harmonize → Navigate → Standards
```

| Layer | Responsibility |
|---|---|
| **Reason** | Extract typed signal from raw data with confidence score |
| **Harmonize** | Deduplicate + rank signals across sources |
| **Navigate** | Choose the single best action path |
| **Standards** | Quality gate — block if confidence < 0.6 or DAG rejects |

---

## 4. DAG Integration

- Every system registers itself via `NodeRegistry.register(SYSTEM_ID)`
- All money/external actions pass through `StandardsGate.evaluate()`
- All executions produce a `ProofCertificate` written to `CausalMemory`
- Mastery events are emitted to `ORCHESTRATOR_WEBHOOK_URL`

---

## 5. ProofCertificate Schema

```json
{
  "cert_id": "<uuid4>",
  "cycle_id": "<uuid4>",
  "system_id": "<SYSTEM_ID>",
  "signal_type": "<string>",
  "action": "<string>",
  "approved": true,
  "value_usd": 0.0,
  "confidence": 0.95,
  "outcome": "executed|blocked|pending",
  "timestamp": "<ISO-8601>",
  "dag_node": "<string>",
  "standards_version": "1.0",
  "fingerprint": "<sha256[:16]>"
}
```

---

## 6. Mastery Gate

A system is considered **mastered** when:

- `confidence >= 0.85` on **50 consecutive cycles**
- System emits `SYSTEM_MASTERED` event to orchestrator
- Orchestrator upgrades system priority in the DAG
- Mastered systems propagate learnings to peer systems via `CausalMemory`

---

## 7. Full-Stack Node Requirements

Every system must expose:

| Layer | Requirement |
|---|---|
| **API** | FastAPI `/health`, `/run`, `/status`, `/proofs` endpoints |
| **Frontend** | Status dashboard (HTML/JS) at `/ui` |
| **Auth** | Bearer token via `GARCAR_API_KEY` env var |
| **Telemetry** | Emit structured JSON logs (cycle_id, signal_type, confidence, outcome) |
| **Memory** | CausalMemory read/write on every cycle |
| **Orchestrator** | Register with NodeRegistry on startup |

---

## 8. Versioning

- Semantic versioning: `MAJOR.MINOR.PATCH`
- Breaking RHNS layer changes → MAJOR bump
- New signal types or actions → MINOR bump  
- Bug fixes + confidence tuning → PATCH bump
- All changes must update `PLATFORM_STANDARD.md` if they affect shared contract

---

## 9. Cross-System Communication

Systems communicate only through:
1. `ORCHESTRATOR_WEBHOOK_URL` event bus (async)
2. `CausalMemory` shared store (sync reads, async writes)
3. REST calls through the Shared API Bank

Direct system-to-system HTTP calls are **not permitted** — all routing goes through the DAG orchestrator.

---

## 10. Continuous Improvement Loop

After every mastery event:
1. `FeedbackLoop.update()` adjusts confidence weights
2. Orchestrator broadcasts updated weights to all peer systems
3. Peer systems absorb weights on next `CausalMemory` read
4. System moves to next mastery tier (Bronze → Silver → Gold → Autonomous)

```
Bronze:    50  consecutive cycles ≥ 0.85
Silver:   200  consecutive cycles ≥ 0.90
Gold:     500  consecutive cycles ≥ 0.95
Autonomous: certified self-improving — no human gate needed
```

---

*Garcar Enterprise · RHNS Platform Standard · v1.0 · April 2026*
