"""
RHNS Symbolic Verifier — Constraint Engine
============================================
Formal constraint verification for the Navigate layer.

Inspired by LOOP architecture: LLM (Navigate) → Symbolic Verifier →
Counterexample feedback → Navigate repair → Standards approval.

The verifier enforces hard rules that override model confidence:
- Rate limiting (no duplicate action within N hours)
- Value thresholds (minimum USD value to trigger action)
- Urgency-action compatibility (only immediate/high urgency triggers expensive actions)
- Source availability (don't fire Stripe actions if STRIPE_SECRET_KEY missing)
- Cooldown enforcement (failed actions go into cooldown)
- Budget guard (total actions per cycle cannot exceed max_actions_per_cycle)
"""

import json
import os
import hashlib
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional


@dataclass
class ConstraintViolation:
    """Represents a single constraint that was violated."""
    rule_id: str
    rule_name: str
    description: str
    severity: str   # hard | soft
    counterexample: str   # What to change to satisfy the constraint


@dataclass
class VerificationResult:
    """Result of running a proposed action through the constraint engine."""
    approved: bool
    action: str
    violations: list[ConstraintViolation] = field(default_factory=list)
    repair_suggestion: str = ""
    verification_id: str = ""
    timestamp: str = ""
    
    def to_dict(self):
        return {
            "approved": self.approved,
            "action": self.action,
            "violations": [asdict(v) for v in self.violations],
            "repair_suggestion": self.repair_suggestion,
            "verification_id": self.verification_id,
            "timestamp": self.timestamp,
        }


class SymbolicVerifier:
    """
    Constraint-based verifier for RHNS Navigate layer outputs.
    
    Runs proposed actions through a set of formal rules before
    the Standards layer executes them. If a hard constraint is
    violated, the action is rejected with a counterexample that
    Navigate can use to generate a repaired action.
    
    This implements the LOOP feedback principle:
    planner → validator → counterexample → planner repair.
    """
    
    # Rule IDs
    RULE_RATE_LIMIT = "RATE_LIMIT_001"
    RULE_MIN_VALUE = "MIN_VALUE_002"
    RULE_URGENCY_COMPAT = "URGENCY_COMPAT_003"
    RULE_SOURCE_AVAIL = "SOURCE_AVAIL_004"
    RULE_COOLDOWN = "COOLDOWN_005"
    RULE_BUDGET_GUARD = "BUDGET_006"
    RULE_CONFIDENCE_FLOOR = "CONF_FLOOR_007"
    RULE_NO_DUPLICATE = "NO_DUPLICATE_008"
    
    def __init__(
        self,
        state_path: str = "rhns/verifier_state.json",
        rate_limit_hours: int = 4,
        min_action_value_usd: float = 5.0,
        max_actions_per_cycle: int = 10,
        confidence_floor: float = 0.55,
        cooldown_hours: int = 2,
    ):
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.rate_limit_hours = rate_limit_hours
        self.min_action_value_usd = min_action_value_usd
        self.max_actions_per_cycle = max_actions_per_cycle
        self.confidence_floor = confidence_floor
        self.cooldown_hours = cooldown_hours
        
        self._state: dict = self._load_state()
        self._cycle_action_count: int = 0
    
    def _load_state(self) -> dict:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text())
            except Exception:
                pass
        return {"actions": {}, "cooldowns": {}}
    
    def _save_state(self):
        self.state_path.write_text(json.dumps(self._state, indent=2))
    
    def _action_fingerprint(self, action: str, signal_type: str) -> str:
        raw = f"{signal_type}:{action[:80]}"
        return hashlib.sha256(raw.encode()).hexdigest()[:20]
    
    def _hours_since(self, iso_timestamp: str) -> float:
        try:
            ts = datetime.fromisoformat(iso_timestamp)
            now = datetime.now(timezone.utc)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return (now - ts).total_seconds() / 3600
        except Exception:
            return 999.0
    
    def _check_rate_limit(self, fingerprint: str) -> Optional[ConstraintViolation]:
        actions = self._state.get("actions", {})
        if fingerprint in actions:
            hours_ago = self._hours_since(actions[fingerprint]["last_fired"])
            if hours_ago < self.rate_limit_hours:
                remaining = self.rate_limit_hours - hours_ago
                return ConstraintViolation(
                    rule_id=self.RULE_RATE_LIMIT,
                    rule_name="Rate Limit",
                    description=f"This action was last fired {hours_ago:.1f}h ago. Minimum interval: {self.rate_limit_hours}h.",
                    severity="hard",
                    counterexample=f"Wait {remaining:.1f}h before re-firing, or target a different customer/resource.",
                )
        return None
    
    def _check_min_value(self, value_usd: float) -> Optional[ConstraintViolation]:
        if value_usd < self.min_action_value_usd and value_usd > 0:
            return ConstraintViolation(
                rule_id=self.RULE_MIN_VALUE,
                rule_name="Minimum Value Threshold",
                description=f"Action value ${value_usd:.2f} is below minimum ${self.min_action_value_usd:.2f}.",
                severity="soft",
                counterexample=f"Batch with other low-value signals until total exceeds ${self.min_action_value_usd:.2f}.",
            )
        return None
    
    def _check_urgency_compat(self, action: str, urgency: str) -> Optional[ConstraintViolation]:
        expensive_keywords = ["CAMPAIGN", "OUTBOUND", "VOICEMAIL", "MULTI_CHANNEL"]
        is_expensive = any(k in action.upper() for k in expensive_keywords)
        if is_expensive and urgency not in ("immediate", "high"):
            return ConstraintViolation(
                rule_id=self.RULE_URGENCY_COMPAT,
                rule_name="Urgency-Action Compatibility",
                description=f"Expensive action '{action[:40]}' triggered for urgency='{urgency}'. Expensive actions require immediate or high urgency.",
                severity="hard",
                counterexample="Downgrade to MONITOR action, or upgrade signal urgency with additional evidence.",
            )
        return None
    
    def _check_source_availability(self, action: str) -> Optional[ConstraintViolation]:
        source_key_map = {
            "STRIPE": "STRIPE_SECRET_KEY",
            "HUBSPOT": "HUBSPOT_API_KEY",
            "SLACK": "SLACK_WEBHOOK_URL",
            "LINEAR": "LINEAR_API_KEY",
        }
        for keyword, env_key in source_key_map.items():
            if keyword in action.upper():
                if not os.getenv(env_key):
                    return ConstraintViolation(
                        rule_id=self.RULE_SOURCE_AVAIL,
                        rule_name="Source Availability",
                        description=f"Action requires {keyword} but {env_key} is not configured.",
                        severity="hard",
                        counterexample=f"Add {env_key} to GitHub Actions secrets, or reroute action to an available source.",
                    )
        return None
    
    def _check_cooldown(self, fingerprint: str) -> Optional[ConstraintViolation]:
        cooldowns = self._state.get("cooldowns", {})
        if fingerprint in cooldowns:
            hours_ago = self._hours_since(cooldowns[fingerprint]["entered_at"])
            if hours_ago < self.cooldown_hours:
                remaining = self.cooldown_hours - hours_ago
                return ConstraintViolation(
                    rule_id=self.RULE_COOLDOWN,
                    rule_name="Cooldown Enforcement",
                    description=f"This action is in cooldown after a previous failure ({hours_ago:.1f}h ago).",
                    severity="hard",
                    counterexample=f"Wait {remaining:.1f}h before retrying. Consider a different action path.",
                )
        return None
    
    def _check_budget(self) -> Optional[ConstraintViolation]:
        if self._cycle_action_count >= self.max_actions_per_cycle:
            return ConstraintViolation(
                rule_id=self.RULE_BUDGET_GUARD,
                rule_name="Cycle Budget Guard",
                description=f"Cycle action budget exhausted ({self.max_actions_per_cycle} actions already approved this cycle).",
                severity="hard",
                counterexample="Queue remaining actions for next cycle, or raise max_actions_per_cycle in config.",
            )
        return None
    
    def _check_confidence(self, confidence: float) -> Optional[ConstraintViolation]:
        if confidence < self.confidence_floor:
            return ConstraintViolation(
                rule_id=self.RULE_CONFIDENCE_FLOOR,
                rule_name="Confidence Floor",
                description=f"Signal confidence {confidence:.2f} is below floor {self.confidence_floor:.2f}.",
                severity="soft",
                counterexample="Gather corroborating signals from additional sources before acting.",
            )
        return None
    
    def verify(
        self,
        action: str,
        signal_type: str,
        urgency: str,
        value_usd: float,
        confidence: float,
        source: str = "",
    ) -> VerificationResult:
        """
        Run all constraints against a proposed action.
        Returns VerificationResult with approval decision and any violations.
        """
        now = datetime.now(timezone.utc).isoformat()
        fingerprint = self._action_fingerprint(action, signal_type)
        verification_id = f"ver_{fingerprint[:8]}_{int(time.time())}"
        
        violations = []
        
        # Run all checks
        checks = [
            self._check_budget(),
            self._check_rate_limit(fingerprint),
            self._check_cooldown(fingerprint),
            self._check_source_availability(action),
            self._check_urgency_compat(action, urgency),
            self._check_min_value(value_usd),
            self._check_confidence(confidence),
        ]
        
        for check in checks:
            if check is not None:
                violations.append(check)
        
        hard_violations = [v for v in violations if v.severity == "hard"]
        approved = len(hard_violations) == 0
        
        repair_suggestion = ""
        if violations:
            repair_parts = [f"[{v.rule_id}] {v.counterexample}" for v in violations[:2]]
            repair_suggestion = " | ".join(repair_parts)
        
        if approved:
            self._cycle_action_count += 1
            # Record the action as fired
            actions = self._state.setdefault("actions", {})
            actions[fingerprint] = {
                "action": action[:80],
                "signal_type": signal_type,
                "last_fired": now,
                "fire_count": actions.get(fingerprint, {}).get("fire_count", 0) + 1,
            }
            self._save_state()
        
        return VerificationResult(
            approved=approved,
            action=action,
            violations=violations,
            repair_suggestion=repair_suggestion,
            verification_id=verification_id,
            timestamp=now,
        )
    
    def enter_cooldown(self, action: str, signal_type: str, reason: str = ""):
        """Put an action into cooldown after a failure is reported."""
        fingerprint = self._action_fingerprint(action, signal_type)
        cooldowns = self._state.setdefault("cooldowns", {})
        cooldowns[fingerprint] = {
            "entered_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
        }
        self._save_state()
    
    def reset_cycle(self):
        """Reset the per-cycle action budget counter."""
        self._cycle_action_count = 0
    
    def get_constraint_summary(self) -> dict:
        """Return current constraint state for monitoring."""
        return {
            "cycle_actions_used": self._cycle_action_count,
            "cycle_budget": self.max_actions_per_cycle,
            "actions_in_rate_limit": len(self._state.get("actions", {})),
            "actions_in_cooldown": len(self._state.get("cooldowns", {})),
            "rules_active": 7,
        }
