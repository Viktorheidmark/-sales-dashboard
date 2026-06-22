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


# Chart type constants — kept in sync with frontend ChartPayload.chart_type
LINE_CHART = "line_chart"
BAR_CHART = "bar_chart"
PIE_CHART = "pie_chart"

# Priority order when multiple tools were called in one turn.
# First matching tool with ≥2 usable rows wins.
CHART_PRIORITY = [
    "get_sales_over_time",
    "get_market_share",
    "get_top_products",
    "get_sales_by_region",
    "get_declining_products",
    # get_supplier_kpis intentionally absent → no chart
]


def _shorten_period(period: str, granularity: str) -> str:
    """
    Convert DATE_TRUNC output to a readable axis label.
    month → "2026-03", week/day → keep as-is (YYYY-MM-DD).
    """
    if granularity == "month" and len(period) == 10:
        return period[:7]   # "2026-01-01" → "2026-01"
    return period


# ---------------------------------------------------------------------------
# Per-tool builders
# ---------------------------------------------------------------------------

def _build_sales_over_time(result: dict) -> Optional[dict]:
    series = result.get("series") or []
    if len(series) < 2:
        return None
    granularity = result.get("granularity", "month")
    dr = result.get("date_range", {})
    title = f"Försäljningstrend {dr.get('start', '')} → {dr.get('end', '')}"
    data = [
        {"label": _shorten_period(p["period"], granularity), "revenue": p["revenue"]}
        for p in series
        if p.get("revenue") is not None
    ]
    if len(data) < 2:
        return None
    return {
        "chart_type": LINE_CHART,
        "title": title,
        "description": f"Intäkt per {granularity}",
        "x_key": "label",
        "y_key": "revenue",
        "data": data,
        "source_tool": "get_sales_over_time",
        "generated_from_row_count": len(data),
    }


def _build_top_products(result: dict) -> Optional[dict]:
    products = result.get("products") or []
    if len(products) < 2:
        return None
    data = [
        {"product_name": p["product_name"], "revenue": p["revenue"]}
        for p in products
        if p.get("revenue") is not None
    ]
    if len(data) < 2:
        return None
    return {
        "chart_type": BAR_CHART,
        "title": f"Topp {len(data)} produkter efter intäkt",
        "description": "Rankade efter intäkt under perioden",
        "x_key": "product_name",
        "y_key": "revenue",
        "data": data,
        "source_tool": "get_top_products",
        "generated_from_row_count": len(data),
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
    dr = result.get("date_range", {})
    return {
        "chart_type": BAR_CHART,
        "title": f"Försäljning per region",
        "description": f"Intäkt per region ({dr.get('start', '')} → {dr.get('end', '')})",
        "x_key": "region",
        "y_key": "revenue",
        "data": data,
        "source_tool": "get_sales_by_region",
        "generated_from_row_count": len(data),
    }


def _build_market_share(result: dict) -> Optional[dict]:
    sup_rev = result.get("supplier_revenue")
    comp_rev = result.get("competitor_aggregate_revenue")
    # Need both slices to make a meaningful pie
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
        "title": f"Marknadsandel: {category}",
        "description": "Vår intäkt vs. aggregerade konkurrenter",
        "x_key": "name",
        "y_key": "revenue",
        "data": data,
        "source_tool": "get_market_share",
        "generated_from_row_count": 2,
    }


def _build_declining_products(result: dict) -> Optional[dict]:
    products = result.get("products") or []
    if len(products) < 2:
        return None
    data = []
    for p in products:
        # Prefer pct change; fall back to absolute change
        value = p.get("revenue_change_pct") if p.get("revenue_change_pct") is not None else p.get("revenue_change")
        if value is not None:
            data.append({"product_name": p["product_name"], "revenue_change_pct": value})
    if len(data) < 2:
        return None
    days = result.get("comparison_days", 30)
    return {
        "chart_type": BAR_CHART,
        "title": f"Produkter med störst nedgång (senaste {days} dagar)",
        "description": "Procentuell intäktförändring vs. föregående period (negativa värden = minskning)",
        "x_key": "product_name",
        "y_key": "revenue_change_pct",
        "data": data,
        "source_tool": "get_declining_products",
        "generated_from_row_count": len(data),
    }


_BUILDERS = {
    "get_sales_over_time": _build_sales_over_time,
    "get_top_products": _build_top_products,
    "get_sales_by_region": _build_sales_by_region,
    "get_market_share": _build_market_share,
    "get_declining_products": _build_declining_products,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_chart(tool_name: str, result: dict) -> Optional[dict]:
    """Build a chart payload for a single MCP tool result. Returns None if not applicable."""
    builder = _BUILDERS.get(tool_name)
    if builder is None:
        return None
    try:
        return builder(result)
    except (KeyError, TypeError, ValueError):
        return None


def pick_chart(tool_results: list[tuple[str, dict]]) -> Optional[dict]:
    """
    Select the single best chart from a list of (tool_name, parsed_result) pairs.

    Priority order follows CHART_PRIORITY — the first tool in that list that
    produces a valid chart (≥2 rows) wins. At most one chart is returned.
    """
    # Build a lookup: tool_name → list of results (a tool may be called multiple times)
    by_tool: dict[str, list[dict]] = {}
    for name, result in tool_results:
        by_tool.setdefault(name, []).append(result)

    for tool_name in CHART_PRIORITY:
        for result in by_tool.get(tool_name, []):
            chart = build_chart(tool_name, result)
            if chart is not None:
                return chart

    return None
