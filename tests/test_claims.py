from rhns.revenue_governance.claims import ClaimValidator
from rhns.revenue_governance.models import CommercialClaim, EvidenceLevel


def test_claim_blocks_guaranteed_language():
    claim = CommercialClaim("Guaranteed ROI for every client.", EvidenceLevel.ESTIMATED, 2, "September 2026", ("stripe:invoice:1",), ("Estimate.",))
    assert not ClaimValidator.validate(claim).allowed


def test_incremental_requires_attribution_tier_two():
    claim = CommercialClaim("Incremental ROI was measured.", EvidenceLevel.ESTIMATED, 1, "September 2026", ("hubspot:deal:1",), ("Traceable only.",))
    assert not ClaimValidator.validate(claim).allowed


def test_public_claim_requires_permission_and_review():
    claim = CommercialClaim("Estimated ROI for the measurement period.", EvidenceLevel.ESTIMATED, 2, "September 2026", ("hubspot:deal:1",), ("Historical baseline.",), public_use=True)
    assert not ClaimValidator.validate(claim).allowed
