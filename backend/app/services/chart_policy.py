"""
Question-to-chart policy — maps analytical intent to visualization behavior.

Charts are chosen from user intent and tool context, not row counts alone.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Optional

from app.services.chart_builder import (
    BAR_CHART,
    LINE_CHART,
    PIE_CHART,
    build_chart,
    build_period_comparison_chart,
    build_time_series_chart,
    build_weekly_kpi_comparison_chart,
    is_relatively_flat_series,
)

_FLAT_REVENUE_PCT_THRESHOLD = 3.0


class ChartIntent(str, Enum):
    TIME_SERIES = "time_series"
    PERIOD_COMPARISON = "period_comparison"
    RANKING = "ranking"
    SINGLE_PRODUCT_DECLINE = "single_product_decline"
    REGION_RANKING = "region_ranking"
    MARKET_SHARE = "market_share"
    WEEKLY_KPI = "weekly_kpi"
    DRIVER_RANKING = "driver_ranking"
    NONE = "none"


_TIME_SERIES_RE = re.compile(
    r"(utvecklat|utveckling|utvecklades|trend|över\s+tid|vecka\s+för\s+vecka|"
    r"dag\s+för\s+dag|daglig|visa\s+trend|försäljningstrend)",
    re.IGNORECASE,
)

_PERIOD_COMPARISON_RE = re.compile(
    r"(jämför.{0,40}(senaste|föregående|förra)|jämfört med förra|"
    r"jämfört med föregående|bättre än föregående|periodjämförelse|"
    r"mot föregående period)",
    re.IGNORECASE,
)

_WEEKLY_FACTUAL_RE = re.compile(
    r"(hur såg försäljningen ut|hur gick veckan|senaste\s+veck)",
    re.IGNORECASE,
)


def _tool_map(tool_results: list[tuple[str, dict]]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for name, result in tool_results:
        if isinstance(result, dict) and "error" not in result:
            out[name] = result
    return out


def _explicit_intent(tool_results: list[tuple[str, dict]]) -> Optional[ChartIntent]:
    found: list[ChartIntent] = []
    for _, result in tool_results:
        raw = result.get("_chart_intent")
        if not raw:
            continue
        try:
            found.append(ChartIntent(raw))
        except ValueError:
            pass
    if ChartIntent.TIME_SERIES in found:
        return ChartIntent.TIME_SERIES
    return found[0] if found else None


def resolve_chart_intent(
    question: str,
    tool_results: list[tuple[str, dict]],
) -> ChartIntent:
    explicit = _explicit_intent(tool_results)
    if explicit:
        return explicit

    tools = _tool_map(tool_results)
    q = (question or "").strip()

    if "get_market_share" in tools:
        return ChartIntent.MARKET_SHARE

    if "get_revenue_drivers" in tools:
        focus = tools["get_revenue_drivers"].get("_deep_dive_focus")
        if focus in ("gainers", "losers", "regions"):
            return ChartIntent.DRIVER_RANKING
        if "get_sales_over_time" in tools or _TIME_SERIES_RE.search(q):
            return ChartIntent.TIME_SERIES
        if _PERIOD_COMPARISON_RE.search(q):
            return ChartIntent.PERIOD_COMPARISON
        if _TIME_SERIES_RE.search(q):
            return ChartIntent.TIME_SERIES
        return ChartIntent.TIME_SERIES

    if "get_declining_products" in tools:
        focus = tools["get_declining_products"].get("_deep_dive_focus")
        if focus == "regions":
            return ChartIntent.REGION_RANKING
        if focus == "portfolio":
            return ChartIntent.RANKING
        if focus == "product_trend":
            return ChartIntent.TIME_SERIES
        return ChartIntent.SINGLE_PRODUCT_DECLINE

    if "get_top_products" in tools:
        return ChartIntent.RANKING

    if "get_sales_by_region" in tools:
        return ChartIntent.REGION_RANKING

    if "get_supplier_kpis" in tools:
        return ChartIntent.PERIOD_COMPARISON

    if "get_sales_over_time" in tools:
        if _WEEKLY_FACTUAL_RE.search(q):
            return ChartIntent.WEEKLY_KPI
        if _PERIOD_COMPARISON_RE.search(q):
            return ChartIntent.PERIOD_COMPARISON
        return ChartIntent.TIME_SERIES

    return ChartIntent.NONE


def select_charts(
    question: str,
    tool_results: list[tuple[str, dict]],
) -> list[dict]:
    """Return ordered chart payloads: primary first, secondary charts after."""
    if not tool_results:
        return []

    intent = resolve_chart_intent(question, tool_results)
    tools = _tool_map(tool_results)
    charts: list[dict] = []

    if intent == ChartIntent.TIME_SERIES:
        sales = tools.get("get_sales_over_time")
        if sales and not sales.get("suppress_chart"):
            trend = build_time_series_chart(sales, force=True)
            if trend:
                charts.append({**trend, "chart_role": "primary"})
        return charts

    if intent == ChartIntent.PERIOD_COMPARISON:
        if "get_revenue_drivers" in tools:
            chart = build_period_comparison_chart(tools["get_revenue_drivers"])
            if chart:
                charts.append({**chart, "chart_role": "primary"})
            return charts
        if "get_supplier_kpis" in tools:
            chart = build_chart("get_supplier_kpis", tools["get_supplier_kpis"])
            if chart:
                charts.append({**chart, "chart_role": "primary"})
            return charts

    if intent == ChartIntent.WEEKLY_KPI:
        sales = tools.get("get_sales_over_time")
        if sales:
            chart = build_weekly_kpi_comparison_chart(sales)
            if chart:
                charts.append({**chart, "chart_role": "primary"})
        return charts

    if intent == ChartIntent.DRIVER_RANKING:
        chart = build_chart("get_revenue_drivers", tools.get("get_revenue_drivers", {}))
        if chart:
            charts.append({**chart, "chart_role": "primary"})
        return charts

    if intent == ChartIntent.SINGLE_PRODUCT_DECLINE:
        declining = tools.get("get_declining_products", {})
        chart = build_chart("get_declining_products", declining)
        if chart:
            charts.append({**chart, "chart_role": "primary"})
        return charts

    if intent == ChartIntent.RANKING:
        for tool_name in ("get_declining_products", "get_top_products"):
            if tool_name in tools:
                chart = build_chart(tool_name, tools[tool_name])
                if chart:
                    charts.append({**chart, "chart_role": "primary"})
                return charts

    if intent == ChartIntent.REGION_RANKING:
        if "get_declining_products" in tools:
            chart = build_chart("get_declining_products", tools["get_declining_products"])
            if chart:
                charts.append({**chart, "chart_role": "primary"})
            return charts
        if "get_sales_by_region" in tools:
            chart = build_chart("get_sales_by_region", tools["get_sales_by_region"])
            if chart:
                charts.append({**chart, "chart_role": "primary"})
            return charts
        if "get_revenue_drivers" in tools:
            chart = build_chart("get_revenue_drivers", tools["get_revenue_drivers"])
            if chart:
                charts.append({**chart, "chart_role": "primary"})
            return charts

    if intent == ChartIntent.MARKET_SHARE:
        chart = build_chart("get_market_share", tools.get("get_market_share", {}))
        if chart:
            charts.append({**chart, "chart_role": "primary"})
        return charts

    # Fallback: legacy priority
    for tool_name in (
        "get_sales_over_time",
        "get_market_share",
        "get_top_products",
        "get_sales_by_region",
        "get_declining_products",
        "get_revenue_drivers",
    ):
        if tool_name in tools:
            chart = build_chart(tool_name, tools[tool_name])
            if chart:
                charts.append({**chart, "chart_role": "primary"})
            break

    return charts


def stability_note_for_series(series: list[dict]) -> Optional[str]:
    if is_relatively_flat_series(series):
        return "Försäljningen var relativt stabil under perioden"
    return None
