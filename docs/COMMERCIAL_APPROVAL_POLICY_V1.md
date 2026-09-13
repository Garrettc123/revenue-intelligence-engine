# Commercial Approval Policy v1

## Default

All external or consequential actions require approval unless explicit policy permits automation. When policy is missing or ambiguous, RHNS fails closed.

## Approval matrix

- Read permitted source data: connector permission and lawful purpose.
- Analyze or draft internally: system policy and trace logging.
- Send external message: resolved recipient, exact content, and authorized approver.
- Create or update CRM record: policy-defined approver; default human review.
- Create internal task: policy-defined approver; default human review.
- Publish web or social content: authorized content approver and exact payload.
- Offer price, discount, credit, or concession: authorized commercial approver.
- Accept scope or legal terms: authorized signatory or delegated approver.
- Create invoice, charge, refund, transfer, or payout: transaction-specific authorized approval.
- Deploy production code: authorized release approver with release-gate evidence.
- Publish ROI or case-study claim: evidence reviewer plus client permission.

## Approval record

Retain proposal ID, requested action, resolved target, exact payload, evidence references, limitations, approver, decision time, expiration if applicable, execution result, and source-system record ID.

Delegation must be explicit, scoped, dated, and revocable.
