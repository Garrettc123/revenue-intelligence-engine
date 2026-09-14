from __future__ import annotations

from .models import ActionClass, ActionProposal, GateDecision


class ApprovalGate:
    ALWAYS_APPROVAL = {ActionClass.EXTERNAL_WRITE, ActionClass.COMMERCIAL_COMMITMENT, ActionClass.FINANCIAL_EXECUTION}

    @classmethod
    def evaluate(cls, proposal: ActionProposal) -> GateDecision:
        if proposal.action_class is ActionClass.PROHIBITED:
            return GateDecision(False, "blocked", ("Action class is prohibited.",))
        if proposal.action_class in cls.ALWAYS_APPROVAL:
            if not proposal.target:
                return GateDecision(False, "blocked", ("Approval-required action needs a resolved target.",))
            if not proposal.payload:
                return GateDecision(False, "blocked", ("Approval-required action needs an exact payload.",))
            if not proposal.approved_by:
                return GateDecision(False, "approval_required", ("Named approval is required before execution.",))
        if proposal.action_class is ActionClass.INTERNAL_WRITE and not proposal.approved_by:
            return GateDecision(False, "approval_required", ("Internal write requires explicit policy approval.",))
        return GateDecision(True, "allowed", ())
