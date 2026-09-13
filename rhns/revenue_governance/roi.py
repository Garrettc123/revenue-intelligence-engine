from __future__ import annotations

from .models import ROICalculationInput, ROICalculationResult


class ROICalculator:
    """Calculates conservative financial outputs and fails closed on missing inputs."""

    @staticmethod
    def calculate(data: ROICalculationInput) -> ROICalculationResult:
        warnings: list[str] = []
        if data.direct_program_cost <= 0:
            return ROICalculationResult(
                attributed_incremental_revenue=data.attributed_incremental_revenue,
                attributed_incremental_gross_profit=None,
                net_contribution=None,
                roi_percent=None,
                payback_months=None,
                currency=data.currency,
                status="blocked",
                warnings=("ROI requires a positive direct program cost.",),
            )
        if data.margin_rate is None:
            return ROICalculationResult(
                attributed_incremental_revenue=data.attributed_incremental_revenue,
                attributed_incremental_gross_profit=None,
                net_contribution=None,
                roi_percent=None,
                payback_months=None,
                currency=data.currency,
                status="conditional",
                warnings=("Profit and ROI are blocked until documented margin evidence is supplied.",),
            )
        if not 0 <= data.margin_rate <= 1:
            return ROICalculationResult(
                attributed_incremental_revenue=data.attributed_incremental_revenue,
                attributed_incremental_gross_profit=None,
                net_contribution=None,
                roi_percent=None,
                payback_months=None,
                currency=data.currency,
                status="blocked",
                warnings=("Margin rate must be between 0 and 1.",),
            )
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
        status = "ready" if not warnings else "conditional"
        return ROICalculationResult(
            attributed_incremental_revenue=data.attributed_incremental_revenue,
            attributed_incremental_gross_profit=gross_profit,
            net_contribution=net_contribution,
            roi_percent=roi_percent,
            payback_months=payback_months,
            currency=data.currency,
            status=status,
            warnings=tuple(warnings),
        )