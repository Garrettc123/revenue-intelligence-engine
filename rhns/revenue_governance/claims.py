from __future__ import annotations

from .models import CommercialClaim, EvidenceLevel, GateDecision


class ClaimValidator:
    BANNED_TERMS = ("guaranteed", "guarantee", "risk-free", "automatic income")

    @classmethod
    def validate(cls, claim: CommercialClaim) -> GateDecision:
        text = claim.text.lower()
        reasons: list[str] = []
        for term in cls.BANNED_TERMS:
            if term in text:
                reasons.append(f"Claim contains prohibited term: {term}.")
        if "profit" in text or "roi" in text:
            if not claim.measurement_period:
                reasons.append("Financial claim requires a measurement period.")
            if not claim.source_references:
                reasons.append("Financial claim requires source references.")
            if not claim.limitations:
                reasons.append("Financial claim requires limitations.")
        if "incremental" in text and claim.attribution_tier < 2:
            reasons.append("Incremental wording requires attribution tier 2 or higher.")
        if "verified" in text and claim.evidence_level is not EvidenceLevel.VERIFIED:
            reasons.append("Verified wording requires verified evidence level.")
        if "typical" in text:
            reasons.append("Typical-results wording requires representative evidence and is blocked by default.")
        if claim.public_use and not claim.client_permission:
            reasons.append("Public claim requires client permission.")
        if claim.public_use and not claim.reviewer_approved:
            reasons.append("Public claim requires reviewer approval.")
        return GateDecision(not reasons, "allowed" if not reasons else "blocked", tuple(reasons))