from rhns.revenue_governance.approvals import ApprovalGate
from rhns.revenue_governance.models import ActionClass, ActionProposal


def test_external_write_requires_resolved_target_payload_and_approval():
    proposal = ActionProposal("p1", ActionClass.EXTERNAL_WRITE, "contact:123", {"body": "Hello"})
    decision = ApprovalGate.evaluate(proposal)
    assert not decision.allowed
    assert decision.status == "approval_required"


def test_external_write_allows_named_approval():
    proposal = ActionProposal("p2", ActionClass.EXTERNAL_WRITE, "contact:123", {"body": "Hello"}, approved_by="authorized_reviewer")
    assert ApprovalGate.evaluate(proposal).allowed


def test_prohibited_action_is_blocked():
    proposal = ActionProposal("p3", ActionClass.PROHIBITED, None, {})
    assert not ApprovalGate.evaluate(proposal).allowed
