from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class EvidenceLevel(str, Enum):
    OBSERVED = "observed"
    TRACEABLE = "traceable"
    ESTIMATED = "estimated"
    RECONCILED = "reconciled"
    VERIFIED = "verified"


class ActionClass(str, Enum):
    OBSERVE = "observe"
    ANALYZE = "analyze"
    DRAFT = "draft"
    INTERNAL_WRITE = "internal_write"
    EXTERNAL_WRITE = "external_write"
    COMMERCIAL_COMMITMENT = "commercial_commitment"
    FINANCIAL_EXECUTION = "financial_execution"
    PROHIBITED = "prohibited"


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    source_system: str
    source_record_id: str
    observed_at: str
    normalized_fact: str
    level: EvidenceLevel = EvidenceLevel.OBSERVED
    data_quality: str = "source_record"
    content_hash: str | None = None
    trace_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MeasurementCharter:
    engagement_id: str
    client_name: str
    baseline_start: str
    baseline_end: str
    intervention_start: str
    intervention_end: str
    primary_metric: str
    financial_metric: str
    source_systems: Sequence[str]
    direct_program_cost: float | None
    currency: str = "USD"
    documented_margin_rate: float | None = None
    margin_source: str | None = None
    attribution_tier: int = 0
    known_limitations: Sequence[str] = field(default_factory=tuple)
    authorized_reviewer: str | None = None


@dataclass(frozen=True)
class ROICalculationInput:
    attributed_incremental_revenue: float
    direct_program_cost: float
    margin_rate: float | None = None
    currency: str = "USD"
    evidence_level: EvidenceLevel = EvidenceLevel.ESTIMATED
    attribution_tier: int = 0
    source_references: Sequence[str] = field(default_factory=tuple)
    limitations: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class ROICalculationResult:
    attributed_incremental_revenue: float
    attributed_incremental_gross_profit: float | None
    net_contribution: float | None
    roi_percent: float | None
    payback_months: float | None
    currency: str
    status: str
    warnings: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class CommercialClaim:
    text: str
    evidence_level: EvidenceLevel
    attribution_tier: int
    measurement_period: str | None
    source_references: Sequence[str]
    limitations: Sequence[str]
    client_permission: bool = False
    reviewer_approved: bool = False
    public_use: bool = False


@dataclass(frozen=True)
class ActionProposal:
    proposal_id: str
    action_class: ActionClass
    target: str | None
    payload: Mapping[str, Any]
    evidence_references: Sequence[str] = field(default_factory=tuple)
    requested_by: str = "rhns"
    approved_by: str | None = None


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    status: str
    reasons: Sequence[str] = field(default_factory=tuple)
