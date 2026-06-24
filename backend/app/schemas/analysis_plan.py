"""Structured analysis plan produced by the AI planner stage."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

AnalysisIntent = Literal[
    "sales_overview",
    "sales_trend",
    "product_ranking",
    "product_comparison",
    "region_ranking",
    "region_trend",
    "market_share",
    "product_decline",
    "product_drilldown",
    "portfolio_change",
    "unknown",
]

TimePeriodKind = Literal[
    "year_to_date",
    "previous_year",
    "rolling_days",
    "rolling_months",
    "exact_range",
    "full_history",
    "previous_completed_week",
    "current_week",
    "unspecified",
]

Metric = Literal["revenue", "orders", "units", "market_share"]
Dimension = Literal["product", "brand", "region", "category", "time"]

ComparisonKind = Literal[
    "none",
    "previous_period",
    "product_vs_product",
    "region_vs_region",
    "category_share",
]

VisualizationPrimary = Literal[
    "line",
    "area",
    "bar_ranked",
    "bar_compare",
    "donut",
    "kpi",
    "none",
]

VisualizationGranularity = Literal["day", "week", "month", "quarter", "auto"]

ALLOWED_METRICS = frozenset({"revenue", "orders", "units", "market_share"})
ALLOWED_DIMENSIONS = frozenset({"product", "brand", "region", "category", "time"})


class TimePeriod(BaseModel):
    kind: TimePeriodKind = "unspecified"
    days: Optional[int] = Field(default=None, ge=1, le=730)
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class AnalysisFilters(BaseModel):
    product_names: list[str] = Field(default_factory=list, max_length=10)
    brand_names: list[str] = Field(default_factory=list, max_length=10)
    regions: list[str] = Field(default_factory=list, max_length=5)
    category: Optional[str] = None


class ComparisonSpec(BaseModel):
    kind: ComparisonKind = "none"
    targets: list[str] = Field(default_factory=list, max_length=5)


class VisualizationSpec(BaseModel):
    primary: VisualizationPrimary = "line"
    granularity: VisualizationGranularity = "auto"


class AnalysisPlan(BaseModel):
    """Raw planner output — validated before normalization."""

    intent: AnalysisIntent = "unknown"
    time_period: TimePeriod = Field(default_factory=TimePeriod)
    metrics: list[str] = Field(default_factory=lambda: ["revenue"])
    dimensions: list[str] = Field(default_factory=list)
    filters: AnalysisFilters = Field(default_factory=AnalysisFilters)
    comparison: ComparisonSpec = Field(default_factory=ComparisonSpec)
    visualization: VisualizationSpec = Field(default_factory=VisualizationSpec)
    needs_deep_dive: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    clarification_needed: bool = False
    clarification_question: Optional[str] = None

    @field_validator("metrics", mode="before")
    @classmethod
    def _sanitize_metrics(cls, v: object) -> list[str]:
        if not isinstance(v, list):
            return ["revenue"]
        out = [m for m in v if isinstance(m, str) and m in ALLOWED_METRICS]
        return out or ["revenue"]

    @field_validator("dimensions", mode="before")
    @classmethod
    def _sanitize_dimensions(cls, v: object) -> list[str]:
        if not isinstance(v, list):
            return []
        return [d for d in v if isinstance(d, str) and d in ALLOWED_DIMENSIONS]


class NormalizedPlanMeta(BaseModel):
    """Safe normalized plan metadata for logging/tests — no secrets."""

    intent: AnalysisIntent
    resolved_start_date: str
    resolved_end_date: str
    period_kind: str
    tools: list[str]
    granularity: str
    chart_intent: Optional[str] = None
    region: Optional[str] = None
    category: Optional[str] = None
    planner_confidence: float = 0.0
    normalization_notes: list[str] = Field(default_factory=list)
