"""
Canonical analytics lifecycle schemas (Phase 1).

These strongly-typed Pydantic models are the single source of truth for an
analytics request as it flows through the orchestration pipeline:

    AnalysisPlan  → produced by the planner, frozen by the validator
    AnalysisResult → canonical normalized output (same periods as the plan)
    VerificationResult → verifier verdict
    ConversationAnalysisContext → compact, safe follow-up state

Design rules enforced here:
* A ``period_comparison`` plan MUST carry exactly two complete, non-overlapping
  ``DateRange`` periods (``ComparisonSpec``). There is no implicit "previous
  period"; rolling windows are explicit via ``comparison_type="rolling"``.
* Tenant/supplier scope is NEVER model-controlled — it is attached to
  ``AnalysisResult`` from authenticated context only, never read from planner
  output.
* ``reasoning_summary`` is a concise operational note safe for logs. It must
  not contain hidden chain-of-thought.

This module is additive and imports nothing from ``app.services`` to avoid
circular dependencies during migration.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Literal vocabularies
# ---------------------------------------------------------------------------

AnalysisIntent = Literal[
    "sales_overview",
    "sales_trend",
    "period_comparison",
    "product_ranking",
    "product_decline",
    "product_performance",
    "region_ranking",
    "region_performance",
    "market_share",
    "category_lookup",
    "revenue_drivers",
    "clarification",
    "unsupported",
]

Metric = Literal[
    "revenue",
    "orders",
    "units",
    "average_order_value",
    "market_share",
]

Dimension = Literal["product", "region", "category", "customer"]

ComparisonType = Literal[
    "custom",
    "rolling",
    "year_over_year",
    "month_over_month",
    "quarter_over_quarter",
]

ComparisonSource = Literal[
    "explicit_free_text",
    "comparison_composer",
    "prior_context",
    "preset",
]

ChartIntent = Literal[
    "none",
    "line",
    "bar",
    "horizontal_bar",
    "donut",
    "comparison_bar",
]

OutputSection = Literal[
    "summary",
    "kpis",
    "trend",
    "comparison",
    "product_drivers",
    "region_drivers",
    "ranking",
    "market_share",
    "data_notes",
]

ClarificationType = Literal[
    "comparison_dates",
    "decline_period",
    "metric",
    "scope",
    "unsupported",
]


# ---------------------------------------------------------------------------
# Period primitives
# ---------------------------------------------------------------------------


class DateRange(BaseModel):
    """An inclusive analyzed window. ``start`` and ``end`` are real dates."""

    start: date
    end: date
    label: Optional[str] = None

    @model_validator(mode="after")
    def _check_order(self) -> "DateRange":
        if self.end < self.start:
            raise ValueError(f"DateRange end {self.end} precedes start {self.start}")
        return self

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def overlaps(self, other: "DateRange") -> bool:
        return self.start <= other.end and other.start <= self.end

    def to_iso_dict(self) -> dict[str, str]:
        out = {"start": self.start.isoformat(), "end": self.end.isoformat()}
        if self.label:
            out["label"] = self.label
        return out


class ComparisonSpec(BaseModel):
    """Exactly two fully-resolved periods plus how they were derived."""

    period_a: DateRange
    period_b: DateRange
    comparison_type: ComparisonType
    source: ComparisonSource

    @model_validator(mode="after")
    def _validate_pair(self) -> "ComparisonSpec":
        # Rolling comparisons are the only ones allowed to be adjacent/contiguous;
        # all others must be non-overlapping distinct windows.
        if self.comparison_type != "rolling" and self.period_a.overlaps(self.period_b):
            raise ValueError(
                "Non-rolling comparison periods must not overlap: "
                f"{self.period_a.to_iso_dict()} vs {self.period_b.to_iso_dict()}"
            )
        return self


# ---------------------------------------------------------------------------
# AnalysisPlan — single source of truth for the request
# ---------------------------------------------------------------------------


class AnalysisPlan(BaseModel):
    """
    Canonical plan emitted by the planner and frozen by the validator.

    No downstream stage may mutate intent, metric, dimensions, filters,
    primary_period, comparison, chart_intent, or output_sections.
    """

    intent: AnalysisIntent
    metric: Optional[Metric] = None
    dimensions: list[Dimension] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)

    primary_period: Optional[DateRange] = None
    comparison: Optional[ComparisonSpec] = None

    chart_intent: ChartIntent = "none"
    output_sections: list[OutputSection] = Field(default_factory=list)

    needs_clarification: bool = False
    clarification_type: Optional[ClarificationType] = None

    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning_summary: str = ""

    @model_validator(mode="after")
    def _coherence(self) -> "AnalysisPlan":
        # A period_comparison must carry a complete two-period spec unless it is
        # explicitly asking for clarification (composer).
        if self.intent == "period_comparison" and not self.needs_clarification:
            if self.comparison is None:
                raise ValueError(
                    "period_comparison plan requires a comparison spec with two periods"
                )

        # Clarification plans must declare a clarification_type and run no tools.
        if self.intent == "clarification":
            if not self.needs_clarification:
                raise ValueError("clarification intent requires needs_clarification=True")
            if self.clarification_type is None:
                raise ValueError("clarification intent requires a clarification_type")

        # If clarification is requested, a type must be present.
        if self.needs_clarification and self.clarification_type is None:
            raise ValueError("needs_clarification=True requires a clarification_type")

        return self

    @property
    def runs_tools(self) -> bool:
        """A plan executes analytics tools only when not awaiting clarification."""
        return not self.needs_clarification and self.intent not in (
            "clarification",
            "unsupported",
        )


# ---------------------------------------------------------------------------
# AnalysisResult — canonical normalized output
# ---------------------------------------------------------------------------


class AnalysisResult(BaseModel):
    """
    Normalized result. Periods here MUST equal the plan's periods exactly.

    Tenant/supplier scope is supplied from authenticated context, never from
    the planner.
    """

    plan_id: str
    tenant_id: str
    supplier_id: str

    resolved_plan: AnalysisPlan

    primary_period: Optional[DateRange] = None
    comparison_period: Optional[DateRange] = None

    kpis: dict[str, Any] = Field(default_factory=dict)
    chart_data: Optional[dict[str, Any]] = None
    product_drivers: list[dict[str, Any]] = Field(default_factory=list)
    region_drivers: list[dict[str, Any]] = Field(default_factory=list)
    rankings: list[dict[str, Any]] = Field(default_factory=list)
    market_share: Optional[dict[str, Any]] = None

    data_bounds: Optional[DateRange] = None
    warnings: list[str] = Field(default_factory=list)
    source_tools: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _periods_match_plan(self) -> "AnalysisResult":
        plan = self.resolved_plan

        # Primary period must match the plan's primary period when both present.
        if plan.primary_period and self.primary_period:
            if (
                plan.primary_period.start != self.primary_period.start
                or plan.primary_period.end != self.primary_period.end
            ):
                raise ValueError(
                    "AnalysisResult.primary_period does not match resolved_plan.primary_period"
                )

        # Comparison: result.comparison_period is Period A (the baseline); it
        # must match the plan's comparison.period_a when a comparison exists.
        if plan.comparison and self.comparison_period:
            pa = plan.comparison.period_a
            if (
                pa.start != self.comparison_period.start
                or pa.end != self.comparison_period.end
            ):
                raise ValueError(
                    "AnalysisResult.comparison_period does not match resolved_plan comparison period_a"
                )
        return self


# ---------------------------------------------------------------------------
# VerificationResult — verifier verdict
# ---------------------------------------------------------------------------


class VerificationResult(BaseModel):
    approved: bool
    severity: Literal["none", "warning", "blocking"]
    issues: list[str] = Field(default_factory=list)
    required_action: Literal[
        "continue",
        "replan",
        "clarify",
        "fallback_safe_response",
    ]
    verified_periods_match: bool
    verified_metric_match: bool
    verified_chart_match: bool
    verified_scope_match: bool

    @model_validator(mode="after")
    def _coherence(self) -> "VerificationResult":
        if self.severity == "blocking" and self.approved:
            raise ValueError("a blocking verification result cannot be approved")
        if not self.approved and self.required_action == "continue":
            raise ValueError("unapproved verification cannot require_action='continue'")
        return self


# ---------------------------------------------------------------------------
# ConversationAnalysisContext — compact, safe follow-up state
# ---------------------------------------------------------------------------


class ConversationAnalysisContext(BaseModel):
    """Minimal, immediate context reused only for direct follow-ups."""

    last_resolved_plan: Optional[AnalysisPlan] = None
    last_result_summary: Optional[dict[str, Any]] = None
    awaiting_clarification: Optional[
        Literal["comparison_dates", "decline_period", "metric", "scope"]
    ] = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )

    @property
    def has_reusable_period(self) -> bool:
        """Only a single-period prior plan provides a reusable window."""
        plan = self.last_resolved_plan
        if plan is None or self.awaiting_clarification is not None:
            return False
        if plan.intent in ("clarification", "unsupported", "period_comparison"):
            return False
        return plan.primary_period is not None
