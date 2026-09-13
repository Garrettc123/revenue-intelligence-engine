from rhns.revenue_governance.claims import ClaimValidator
from rhns.revenue_governance.models import CommercialClaim, EvidenceLevel


def test_claim_blocks_guaranteed_language():
    claim = CommercialClaim(
        text="Guaranteed ROI for every client.",
        evidence_level=EvidenceLevel.ESTIMATED,
        attribution_tier=2,
        measurement_period="September 2026",
        source_references=("stripe:invoice:1",),
        limitations=("Estimate.",),
    )
    assert not ClaimValidator.validate(claim).allowed


def test_incremental_requires_attribution_tier_two():
    claim = CommercialClaim(
        text="Incremental ROI was measured.",
        evidence_level=EvidenceLevel.ESTIMATED,
        attribution_tier=1,
        measurement_period="September 2026",
        source_references=("hubspot:deal:1",),
        limitations=("Traceable only.",),
    )
    assert not ClaimValidator.validate(claim).allowed


def test_public_claim_requires_permission_and_review():
    claim = CommercialClaim(
        text="Estimated ROI for the measurement period.",
        evidence_level=EvidenceLevel.ESTIMATED,
        attribution_tier=2,
        measurement_period="September 2026",
        source_references=("hubspot:deal:1",),
        limitations=("Historical baseline.",),
        public_use=True,
    )
    assert not ClaimValidator.validate(claim).allowed