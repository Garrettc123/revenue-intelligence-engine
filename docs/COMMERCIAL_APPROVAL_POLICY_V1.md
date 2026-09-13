# Commercial Approval Policy v1

## Default

All external or consequential actions require approval unless this policy explicitly permits an automated action. When policy is missing or ambiguous, RHNS must fail closed.

## Approval matrix

| Action | Required approval |
|---|---|
| Read permitted source data | Connector permission and lawful purpose |
| Analyze or draft internally | System policy and trace logging |
| Send an external message | Resolved recipient, exact content, authorized approver |
| Create or update a CRM record | Policy-defined approver; default is human review |
| Create an internal task | Policy-defined approver; default is human review |
| Publish a website or social post | Authorized content approver and exact publish payload |
| Offer price, discount, credit, or concession | Authorized commercial approver |
| Accept scope or legal terms | Authorized signatory or delegated approver |
| Create invoice, charge, refund, transfer, or payout | Transaction-specific authorized approval |
| Deploy production code | Authorized release approver with release-gate evidence |
| Publish ROI/case study claim | Evidence reviewer plus client permission |

## Approval record

Every required approval must retain:

- Proposal ID and requested action.
- Resolved target and exact payload.
- Evidence references and limitations.
- Named approver and timestamp.
- Approval decision and expiration if applicable.
- Execution result and source-system record ID.

## Delegation

Delegation must be explicit, scoped, dated, and revocable. A delegated approver may not approve outside the stated action class, client, monetary limit, or period.

## Emergency rule

An emergency does not authorize financial, contractual, or deceptive action. Emergency responses may only preserve safety, data integrity, or system availability and must be logged and reviewed.