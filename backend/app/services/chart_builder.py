"""
Deterministic chart builder — converts raw MCP tool results into chart payloads.

Rules:
- Chart values come ONLY from validated MCP tool output.
- The LLM response text is never parsed for numbers.
- Returns None when the data has fewer than two usable rows.
- get_supplier_kpis never produces a chart.
- Competitor detail is never surfaced beyond what the MCP query already hides.
"""

from typing import Optional

from app.services.period_utils import (
    apply_sales_over_time_period_policy,
    format_date_range_sv,
    format_date_sv,
)

LINE_CHART = "line_chart"
BAR_CHART = "bar_chart"
PIE_CHART = "pie_chart"

CHART_PRIORITY = [
    "get_sales_over_time",
    "get_market_share",
    "get_top_products",
    "get_sales_by_region",
    "get_declining_products",
]

_LABEL_MAX = 22
_DECLINE_CHART_THRESHOLD_PCT = -5.0


def _truncate_label(text: str, max_len: int = _LABEL_MAX) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _shorten_period(period: str, granularity: str) -> str:
    if granularity == "month" and len(period) == 10:
        return period[:7]
    return period


def _granularity_label(granularity: str) -> str:
    return {"day": "dag", "week": "vecka", "month": "månad"}.get(granularity, granularity)


def _build_sales_over_time(result: dict) -> Optional[dict]:
    result = apply_sales_over_time_period_policy(result)
    series = result.get("series") or []
    if len(series) < 2:
        return None
    granularity = result.get("granularity", "month")
    gran_label = _granularity_label(granularity)
    data = [
        {"label": _shorten_period(p["period"], granularity), "revenue": p["revenue"]}
        for p in series
        if p.get("revenue") is not None
    ]
    if len(data) < 2:
        return None

    chart_context = result.get("chart_context") or {}
    period_analysis = result.get("period_analysis") or {}
    widened = chart_context.get("widened")
    lookback_weeks = chart_context.get("lookback_weeks", 8)

    if widened and granularity == "week":
        orig = chart_context.get("original_date_range") or {}
        week_end = orig.get("end") or (result.get("date_range") or {}).get("end")
        if not week_end and data:
            from datetime import date, timedelta
            last_monday = date.fromisoformat(str(data[-1]["label"])[:10])
            week_end = (last_monday + timedelta(days=6)).isoformat()
        title = "Utveckling inför senaste avslutade vecka"
        end_label = format_date_sv(week_end) if week_end else "senaste avslutade vecka"
        description = (
            f"{lookback_weeks} avslutade veckor fram till och med {end_label}"
        )
        period_note = description
    else:
        title = "Omsättningstrend"
        description = f"Omsättning per {gran_label} (fullständiga perioder)"
        period_note = None
        if period_analysis.get("analysed_range_label"):
            period_note = period_analysis["analysed_range_label"]
        elif period_analysis.get("completed_week_label"):
            period_note = period_analysis["completed_week_label"]
        elif period_analysis.get("excluded_incomplete_period"):
            period_note = f"Pågående {gran_label} exkluderad från diagrammet."

    return {
        "chart_type": LINE_CHART,
        "title": title,
        "description": description,
        "x_key": "label",
        "y_key": "revenue",
        "data": data,
        "source_tool": "get_sales_over_time",
        "generated_from_row_count": len(data),
        "period_note": period_note,
    }


def _build_top_products(result: dict) -> Optional[dict]:
    products = result.get("products") or []
    if len(products) < 2:
        return None
    data = []
    for p in products:
        if p.get("revenue") is None:
            continue
        name = p["product_name"]
        data.append({
            "product_name": name,
            "display_label": _truncate_label(name),
            "revenue": p["revenue"],
        })
    if len(data) < 2:
        return None

    region = result.get("region_filter")
    subtitle = "Omsättning per produkt"
    if region:
        subtitle = f"Omsättning per produkt · {region}"

    return {
        "chart_type": BAR_CHART,
        "layout": "horizontal",
        "title": "Topprodukter",
        "description": subtitle,
        "x_key": "display_label",
        "y_key": "revenue",
        "tooltip_key": "product_name",
        "data": data,
        "source_tool": "get_top_products",
        "generated_from_row_count": len(data),
        "emphasis_index": 0,
    }


def _build_sales_by_region(result: dict) -> Optional[dict]:
    regions = result.get("regions") or []
    if len(regions) < 2:
        return None
    data = [
        {"region": r["region"], "revenue": r["revenue"]}
        for r in regions
        if r.get("revenue") is not None
    ]
    if len(data) < 2:
        return None
    return {
        "chart_type": BAR_CHART,
        "layout": "horizontal",
        "title": "Regional försäljning",
        "description": "Omsättning per region",
        "x_key": "region",
        "y_key": "revenue",
        "data": data,
        "source_tool": "get_sales_by_region",
        "generated_from_row_count": len(data),
        "emphasis_index": 0,
    }


def _build_market_share(result: dict) -> Optional[dict]:
    sup_rev = result.get("supplier_revenue")
    comp_rev = result.get("competitor_aggregate_revenue")
    if sup_rev is None or comp_rev is None:
        return None
    if (sup_rev + comp_rev) <= 0:
        return None
    category = result.get("category_name", "kategorin")
    data = [
        {"name": "Oss", "revenue": round(sup_rev, 2)},
        {"name": "Konkurrenter", "revenue": round(comp_rev, 2)},
    ]
    return {
        "chart_type": PIE_CHART,
        "title": "Marknadsandel",
        "description": f"Fördelning i {category}",
        "x_key": "name",
        "y_key": "revenue",
        "data": data,
        "source_tool": "get_market_share",
        "generated_from_row_count": 2,
    }


def _build_declining_products(result: dict) -> Optional[dict]:
    products = result.get("products") or []
    data = []
    for p in products:
        value = p.get("revenue_change_pct")
        if value is None:
            value = p.get("revenue_change")
        if value is None:
            continue
        if isinstance(value, (int, float)) and value > _DECLINE_CHART_THRESHOLD_PCT:
            continue
        name = p["product_name"]
        data.append({
            "product_name": name,
            "display_label": _truncate_label(name),
            "revenue_change_pct": value,
        })
    if len(data) < 1:
        return None
    days = result.get("comparison_days", 30)
    return {
        "chart_type": BAR_CHART,
        "layout": "horizontal",
        "title": "Produkter i nedgång",
        "description": f"Omsättningsförändring % · senaste {days} dagar",
        "x_key": "display_label",
        "y_key": "revenue_change_pct",
        "tooltip_key": "product_name",
        "data": data,
        "source_tool": "get_declining_products",
        "generated_from_row_count": len(data),
        "emphasis_index": 0,
    }


_BUILDERS = {
    "get_sales_over_time": _build_sales_over_time,
    "get_top_products": _build_top_products,
    "get_sales_by_region": _build_sales_by_region,
    "get_market_share": _build_market_share,
    "get_declining_products": _build_declining_products,
}


def build_chart(tool_name: str, result: dict) -> Optional[dict]:
    builder = _BUILDERS.get(tool_name)
    if builder is None:
        return None
    try:
        return builder(result)
    except (KeyError, TypeError, ValueError):
        return None


def pick_chart(tool_results: list[tuple[str, dict]]) -> Optional[dict]:
    by_tool: dict[str, list[dict]] = {}
    for name, result in tool_results:
        by_tool.setdefault(name, []).append(result)

    for tool_name in CHART_PRIORITY:
        for result in by_tool.get(tool_name, []):
            chart = build_chart(tool_name, result)
            if chart is not None:
                return chart

    return None
