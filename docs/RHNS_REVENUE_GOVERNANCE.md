# RHNS Revenue Governance v1

## Purpose

RHNS Revenue Governance converts revenue signals into evidence-backed recommendations and human-approved actions. It does not guarantee sales, revenue, profit, savings, conversion, or return on investment.

## Operating rule

> No fact without a source. No claim without a method. No consequential action without the authority required by policy.

## Decision chain

```text
Source event -> normalized evidence -> analysis -> action proposal -> approval -> execution -> observed outcome -> proof record
```

The system must preserve the distinction between a fact, an inference, a recommendation, an approved action, and a financial claim.

## Action classes

- `observe`: read a permitted source record.
- `analyze`: score, compare, summarize, or calculate internally.
- `draft`: produce a proposed message, document, or task.
- `internal_write`: change an internal record.
- `external_write`: change a third-party or client-facing record.
- `commercial_commitment`: pricing, discount, scope, contract, invoice, or payment-plan decision.
- `financial_execution`: charge, refund, transfer, purchase, trade, swap, or payout.
- `prohibited`: action violates policy.

## Evidence levels

- **observed**: direct source-system record.
- **traceable**: source record linked to a workflow or approved action.
- **estimated**: result calculated from disclosed inputs and assumptions.
- **reconciled**: calculation checked against source records.
- **verified**: reconciled result reviewed by required authorized reviewers.

Evidence cannot be upgraded by model confidence, user preference, or sales value.

## Required controls

- Store source reference, source timestamp, collection timestamp, data-quality level, and evidence hash for material evidence.
- Record methodology and calculator versions for every financial calculation.
- Require direct program cost before calculating ROI.
- Require a documented margin source before reporting gross profit or profit ROI.
- Require attribution tier and limitation disclosure for incremental or causal language.
- Require client permission and claim approval before public case-study use.
- Fail closed when authority, data, evidence, or required approval is missing.

## Human authority

RHNS may observe, analyze, and draft according to policy. Authorized humans approve external communications, public claims, CRM writes where required, pricing, discounts, scope changes, contracts, invoices, charges, refunds, deployments, and financial actions.
