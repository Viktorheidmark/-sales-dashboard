"""
Capability registry — declares which backend tool/query satisfies which plan,
what the plan must provide, and which dimensions/charts are allowed.

The executor reads this registry to map a *validated* plan into typed tool
inputs. The AI never chooses raw function arguments or SQL; it may only select a
registered capability (intent), and even that is validated deterministically.
"""

from __future__ import annotations

from typing import Any

from app.analytics.schemas import AnalysisIntent, ChartIntent

# Required plan fields are expressed as dotted paths understood by the validator.
CAPABILITIES: dict[str, dict[str, Any]] = {
    "period_comparison": {
        "tool": "get_supplier_kpis",  # invoked once per period (A and B)
        "required": ["comparison.period_a", "comparison.period_b"],
        "allowed_dimensions": ["product", "region"],
        "allowed_charts": ["comparison_bar"],
        "default_metric": "revenue",
    },
    "sales_trend": {
        "tool": "get_sales_over_time",
        "required": ["primary_period"],
        "allowed_dimensions": [],
        "allowed_charts": ["line"],
        "default_metric": "revenue",
    },
    "product_ranking": {
        "tool": "get_top_products",
        "required": ["primary_period"],
        "allowed_dimensions": ["product"],
        "allowed_charts": ["horizontal_bar"],
        "supports_sort": ["ascending", "descending"],
        "default_metric": "revenue",
    },
    "product_decline": {
        "tool": "get_declining_products",
        "required": ["primary_period", "comparison"],
        "allowed_dimensions": ["product", "region"],
        "allowed_charts": ["horizontal_bar", "line"],
        "default_metric": "revenue",
    },
    "market_share": {
        "tool": "get_market_share",
        "required": ["primary_period"],
        "allowed_dimensions": ["category"],
        "allowed_charts": ["donut"],
        "default_metric": "market_share",
    },
    "region_ranking": {
        "tool": "get_sales_by_region",
        "required": ["primary_period"],
        "allowed_dimensions": ["region"],
        "allowed_charts": ["horizontal_bar"],
        "default_metric": "revenue",
    },
}

# Capabilities currently routed through the new orchestrator. Everything else
# falls back to the legacy pipeline during migration.
MIGRATED_CAPABILITIES: frozenset[str] = frozenset({"period_comparison"})


def capability_for(intent: AnalysisIntent) -> dict[str, Any] | None:
    return CAPABILITIES.get(intent)


def is_migrated(intent: AnalysisIntent) -> bool:
    return intent in MIGRATED_CAPABILITIES


def chart_intent_allowed(intent: AnalysisIntent, chart_intent: ChartIntent) -> bool:
    cap = CAPABILITIES.get(intent)
    if cap is None:
        return chart_intent == "none"
    if chart_intent == "none":
        return True
    return chart_intent in cap.get("allowed_charts", [])
