from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class VerticalGenome:
    name: str
    target_buyers: Sequence[str]
    core_revenue_leaks: Sequence[str]
    primary_metrics: Sequence[str]
    prohibited_actions: Sequence[str]
    approval_requirements: Mapping[str, str]
    raw: Mapping[str, Any]

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "VerticalGenome":
        return cls(
            name=str(data["vertical"]),
            target_buyers=tuple(data.get("target_buyers", ())),
            core_revenue_leaks=tuple(data.get("core_revenue_leaks", ())),
            primary_metrics=tuple(data.get("primary_metrics", ())),
            prohibited_actions=tuple(data.get("prohibited_actions", ())),
            approval_requirements=dict(data.get("approval_requirements", {})),
            raw=dict(data),
        )
