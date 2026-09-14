from __future__ import annotations

from .models import ROICalculationInput, ROICalculationResult


class ROICalculator:
    """Calculates conservative financial outputs and fails closed on missing inputs."""

    @staticmethod
    def calculate(data: ROICalculationInput) -> ROICalculationResult:
        warnings: list[str] = []
        if data.direct_program_cost <= 0:
            return ROICalculationResult(data.attributed_incremental_revenue, None, None, None, None, data.currency, "blocked", ("ROI requires a positive direct program cost.",))
        if data.margin_rate is None:
            return ROICalculationResult(data.attributed_incremental_revenue, None, None, None, None, data.currency, "conditional", ("Profit and ROI are blocked until documented margin evidence is supplied.",))
        if not 0 <= data.margin_rate <= 1:
            return ROICalculationResult(data.attributed_incremental_revenue, None, None, None, None, data.currency, "blocked", ("Margin rate must be between 0 and 1.",))
        if data.attribution_tier < 2:
            warnings.append("Result is not eligible for incremental or causal wording.")
        if not data.source_references:
            warnings.append("No source references were supplied.")
        if not data.limitations:
            warnings.append("No limitations were supplied.")
        gross_profit = data.attributed_incremental_revenue * data.margin_rate
        net_contribution = gross_profit - data.direct_program_cost
        roi_percent = (net_contribution / data.direct_program_cost) * 100
        payback_months = data.direct_program_cost / gross_profit if gross_profit > 0 else None
        return ROICalculationResult(data.attributed_incremental_revenue, gross_profit, net_contribution, roi_percent, payback_months, data.currency, "ready" if not warnings else "conditional", tuple(warnings))
