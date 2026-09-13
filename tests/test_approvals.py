from rhns.revenue_governance.approvals import ApprovalGate
from rhns.revenue_governance.models import ActionClass, ActionProposal


def test_external_write_requires_resolved_target_payload_and_approval():
    proposal = ActionProposal(
        proposal_id="p1",
        action_class=ActionClass.EXTERNAL_WRITE,
        target="contact:123",
        payload={"body": "Hello"},
    )
    decision = ApprovalGate.evaluate(proposal)
    assert not decision.allowed
    assert decision.status == "approval_required"


def test_external_write_allows_named_approval():
    proposal = ActionProposal(
        proposal_id="p2",
        action_class=ActionClass.EXTERNAL_WRITE,
        target="contact:123",
        payload={"body": "Hello"},
        approved_by="authorized_reviewer",
    )
    assert ApprovalGate.evaluate(proposal).allowed


def test_prohibited_action_is_blocked():
    proposal = ActionProposal(
        proposal_id="p3",
        action_class=ActionClass.PROHIBITED,
        target=None,
        payload={},
    )
    assert not ApprovalGate.evaluate(proposal).allowed