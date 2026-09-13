# RHNS Revenue Governance v1

## Purpose

RHNS Revenue Governance turns revenue signals into evidence-backed recommendations and human-approved actions. It is designed to improve operational control, not to guarantee sales, profit, savings, conversion, or return on investment.

## Operating rule

> No fact without a source. No claim without a method. No consequential action without the authority required by policy.

## Decision chain

```text
Source event → normalized evidence → analysis → action proposal → approval → execution → observed outcome → proof record
```

The system must preserve the distinction between a fact, an inference, a recommendation, an approved action, and a financial claim.

## Action classes

| Class | Meaning | Default handling |
|---|---|---|
| observe | Read a permitted source record | Allowed when connector permission permits |
| analyze | Score, compare, summarize, or calculate internally | Allowed with trace logging |
| draft | Produce a proposed message, document, or task | Allowed internally; never sent automatically |
| internal_write | Change an internal record | Approval required unless an explicit policy permits it |
| external_write | Change a third-party or client-facing record | Explicit action-specific approval required |
| commercial_commitment | Pricing, discount, scope, contract, invoice, or payment-plan decision | Authorized commercial approval required |
| financial_execution | Charge, refund, transfer, purchase, trade, swap, or payout | Transaction-specific authorization required |
| prohibited | Action violates policy | Reject and log |

## Evidence levels

- **observed**: direct source system record.
- **traceable**: source record linked to a workflow or approved action.
- **estimated**: result calculated from disclosed inputs and assumptions.
- **reconciled**: calculation checked against source records.
- **verified**: reconciled result reviewed by required authorized reviewers.

An evidence level cannot be upgraded by model confidence, user preference, or sales value.

## Required controls

- Store source reference, source timestamp, collection timestamp, data-quality level, and evidence hash for material evidence.
- Record methodology version and calculator version for every financial calculation.
- Require direct program cost before calculating ROI.
- Require a documented margin source before describing a result as gross profit or profit ROI.
- Require attribution tier and limitation disclosure for incremental or causal language.
- Require client permission and claim approval before public use of a case study or testimonial.
- Fail closed when authority, data, evidence, or required approval is missing.

## Prohibited behavior

RHNS must reject false scarcity, fabricated testimonials, undisclosed material terms, misleading pricing, impersonation, post-opt-out outreach, concealment of commercial intent, unsupported earnings claims, and autonomous legal, commercial, or financial commitments.

## Human authority

RHNS may observe, analyze, and draft according to policy. Authorized humans approve external communications, public claims, CRM writes where required, pricing, discounts, scope changes, contracts, invoices, charges, refunds, deployments, and financial actions.