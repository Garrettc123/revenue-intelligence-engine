"""
RHNS Constraint Rule Registry
================================
Declarative rule definitions for the symbolic verifier.
Add new rules here without modifying SymbolicVerifier.
"""

from dataclasses import dataclass
from typing import Callable, Any


@dataclass
class ConstraintRule:
    rule_id: str
    name: str
    severity: str   # hard | soft
    description: str
    check_fn: Callable  # fn(context: dict) -> str | None  (None = pass, str = violation message)


# Context keys available to all rules:
# context["action"], context["signal_type"], context["urgency"],
# context["value_usd"], context["confidence"], context["source"],
# context["env"], context["history"]

BUILTIN_RULES: list[ConstraintRule] = [
    ConstraintRule(
        rule_id="CUSTOM_001",
        name="No Negative Value Actions",
        severity="hard",
        description="Actions must not target negative or zero-value signals unless signal_type is system_health.",
        check_fn=lambda ctx: (
            "Action targets zero or negative value — skip unless signal_type is system_health."
            if ctx["value_usd"] < 0 and ctx["signal_type"] != "system_health"
            else None
        ),
    ),
    ConstraintRule(
        rule_id="CUSTOM_002",
        name="Heartbeat Pass-Through",
        severity="soft",
        description="Heartbeat signals should only log, never trigger external actions.",
        check_fn=lambda ctx: (
            "Heartbeat signal should route to MONITOR, not external action."
            if ctx["signal_type"] == "heartbeat" and "MONITOR" not in ctx["action"].upper()
            else None
        ),
    ),
]
