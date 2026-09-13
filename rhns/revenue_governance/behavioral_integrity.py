from __future__ import annotations

from .models import GateDecision


class BehavioralIntegrityGate:
    PROHIBITED_PATTERNS = (
        "act now before it is gone",
        "only one spot left",
        "guaranteed revenue",
        "guaranteed roi",
        "you cannot afford to wait",
        "everyone else is doing it",
        "no risk",
        "secret method",
    )

    @classmethod
    def evaluate_message(cls, text: str, opted_out: bool = False) -> GateDecision:
        reasons: list[str] = []
        if opted_out:
            reasons.append("Recipient has opted out or requested no contact.")
        lower_text = text.lower()
        for pattern in cls.PROHIBITED_PATTERNS:
            if pattern in lower_text:
                reasons.append(f"Message contains prohibited influence pattern: {pattern}.")
        return GateDecision(not reasons, "allowed" if not reasons else "blocked", tuple(reasons))