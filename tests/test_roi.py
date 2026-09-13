from rhns.revenue_governance.models import ROICalculationInput
from rhns.revenue_governance.roi import ROICalculator


def test_roi_requires_positive_cost():
    result = ROICalculator.calculate(ROICalculationInput(10000, 0, 0.3))
    assert result.status == "blocked"
    assert result.roi_percent is None


def test_profit_requires_margin_evidence():
    result = ROICalculator.calculate(ROICalculationInput(10000, 1000, None))
    assert result.status == "conditional"
    assert result.attributed_incremental_gross_profit is None


def test_roi_calculates_from_gross_profit_not_revenue():
    result = ROICalculator.calculate(
        ROICalculationInput(
            attributed_incremental_revenue=10000,
            direct_program_cost=1000,
            margin_rate=0.3,
            attribution_tier=2,
            source_references=("hubspot:deal:1",),
            limitations=("Historical comparison only.",),
        )
    )
    assert result.attributed_incremental_gross_profit == 3000
    assert result.net_contribution == 2000
    assert result.roi_percent == 200