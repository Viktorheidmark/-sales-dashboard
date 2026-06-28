"""
Deterministic validation layer — runs after planning, before any tool executes.

It converts unsafe or incomplete plans into clarification responses rather than
guessing. For the comparison capability it guarantees:
* exactly two complete periods,
* periods inside available data bounds,
* no silent period mutation,
* a chart intent compatible with the analysis intent.

The validator never contacts the model and never reads tenant scope from plan
content (scope is applied by the executor from authenticated context).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from app.analytics.registry import capability_for, chart_intent_allowed
from app.analytics.schemas import AnalysisPlan, ClarificationType, DateRange
from app.services.period_utils import default_data_bounds


@dataclass
class ValidationOutcome:
    ok: bool
    plan: AnalysisPlan
    issues: list[str] = field(default_factory=list)
    needs_clarification: bool = False
    clarification_type: Optional[ClarificationType] = None

    @property
    def approved(self) -> bool:
        return self.ok and not self.needs_clarification


def _clarify(plan: AnalysisPlan, clarification_type: ClarificationType, issue: str) -> ValidationOutcome:
    return ValidationOutcome(
        ok=False,
        plan=plan,
        issues=[issue],
        needs_clarification=True,
        clarification_type=clarification_type,
    )


def _within_bounds(period: DateRange, data_min: date, data_max: date) -> bool:
    # A period must intersect available data to be analyzable.
    return period.end >= data_min and period.start <= data_max


def validate_plan(
    plan: AnalysisPlan,
    data_bounds: Optional[tuple[date, date]] = None,
) -> ValidationOutcome:
    """Validate a planned analysis. Returns an outcome; never raises on bad input."""
    # A clarification plan is already a safe terminal state.
    if plan.needs_clarification or plan.intent == "clarification":
        return ValidationOutcome(
            ok=True,
            plan=plan,
            needs_clarification=True,
            clarification_type=plan.clarification_type or "comparison_dates",
        )

    if plan.intent == "unsupported":
        return _clarify(plan, "unsupported", "Unsupported request.")

    cap = capability_for(plan.intent)
    if cap is None:
        return _clarify(plan, "unsupported", f"No capability registered for intent '{plan.intent}'.")

    # Chart/intent compatibility.
    if not chart_intent_allowed(plan.intent, plan.chart_intent):
        return ValidationOutcome(
            ok=False,
            plan=plan,
            issues=[f"chart_intent '{plan.chart_intent}' incompatible with intent '{plan.intent}'."],
        )

    data_min, data_max = data_bounds or default_data_bounds()

    if plan.intent == "period_comparison":
        return _validate_comparison(plan, data_min, data_max)

    # Non-comparison capabilities: require a primary period.
    if "primary_period" in cap.get("required", []) and plan.primary_period is None:
        return _clarify(plan, "scope", f"intent '{plan.intent}' requires a primary period.")
    return ValidationOutcome(ok=True, plan=plan)


def _validate_comparison(plan: AnalysisPlan, data_min: date, data_max: date) -> ValidationOutcome:
    spec = plan.comparison
    if spec is None:
        return _clarify(plan, "comparison_dates", "Comparison requires two periods.")

    # Two complete periods (schema already guarantees start<=end and non-overlap
    # for non-rolling). Confirm both are inside available data bounds.
    for label, period in (("Period A", spec.period_a), ("Period B", spec.period_b)):
        if not _within_bounds(period, data_min, data_max):
            return _clarify(
                plan,
                "comparison_dates",
                f"{label} {period.to_iso_dict()} is outside available data "
                f"({data_min.isoformat()}–{data_max.isoformat()}).",
            )

    # Non-rolling comparisons must be distinct windows (defense-in-depth; schema
    # also enforces this).
    if spec.comparison_type != "rolling" and spec.period_a.overlaps(spec.period_b):
        return _clarify(plan, "comparison_dates", "Comparison periods overlap.")

    return ValidationOutcome(ok=True, plan=plan)
