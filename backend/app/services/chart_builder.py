"""
Deterministic chart builder — converts raw MCP tool results into chart payloads.

Chart selection is governed by chart_policy.select_charts (intent-based).
"""

from typing import Optional

from app.services.period_utils import (
    apply_sales_over_time_period_policy,
    format_date_sv,
)

LINE_CHART = "line_chart"
BAR_CHART = "bar_chart"
PIE_CHART = "pie_chart"

_FLAT_REVENUE_PCT_THRESHOLD = 3.0
_FLAT_SERIES_CV_THRESHOLD = 0.05

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


def is_relatively_flat_series(series: list[dict]) -> bool:
    revs = [float(p.get("revenue") or 0) for p in series if p.get("revenue") is not None]
    if len(revs) < 2:
        return False
    mean = sum(revs) / len(revs)
    if mean <= 0:
        return False
    spread = max(revs) - min(revs)
    if spread / mean >= _FLAT_SERIES_CV_THRESHOLD * 2:
        return False
    first, last = revs[0], revs[-1]
    if first > 0 and abs((last - first) / first * 100) >= _FLAT_REVENUE_PCT_THRESHOLD:
        return False
    return True


def _compute_highlights(data: list[dict]) -> Optional[dict]:
    if len(data) < 2:
        return None
    valid = [(row["label"], float(row["revenue"])) for row in data if row.get("revenue") is not None]
    if len(valid) < 2:
        return None

    peak_label, peak_rev = max(valid, key=lambda x: x[1])
    trough_label, trough_rev = min(valid, key=lambda x: x[1])
    first_rev = valid[0][1]
    last_rev = valid[-1][1]
    change_pct = round((last_rev - first_rev) / first_rev * 100, 1) if first_rev > 0 else 0.0

    return {
        "peak_label": peak_label,
        "peak_revenue": round(peak_rev, 2),
        "trough_label": trough_label,
        "trough_revenue": round(trough_rev, 2),
        "first_revenue": round(first_rev, 2),
        "last_revenue": round(last_rev, 2),
        "change_pct": change_pct,
    }


def build_period_comparison_chart(
    result: dict,
    *,
    compact: bool = False,
) -> Optional[dict]:
    days = result.get("comparison_days", 30)
    current = result.get("current_period") or {}
    prior = result.get("prior_period") or {}
    curr_rev = float(current.get("total_revenue") or 0)
    prior_rev = float(prior.get("total_revenue") or 0)
    if prior_rev <= 0 and curr_rev <= 0:
        return None
    rev_pct = round(100.0 * (curr_rev - prior_rev) / prior_rev, 1) if prior_rev > 0 else 0.0
    sign = "+" if rev_pct >= 0 else ""
    title = "Periodjämförelse" if not compact else "Jämfört med föregående period"
    return {
        "chart_type": BAR_CHART,
        "chart_variant": "decline_comparison",
        "title": title,
        "description": f"{sign}{rev_pct:.1f} % omsättningsförändring · senaste {days} dagar",
        "data": [
            {"period": "Föregående period", "revenue": round(prior_rev, 2)},
            {"period": "Senaste period", "revenue": round(curr_rev, 2)},
        ],
        "x_key": "period",
        "y_key": "revenue",
        "source_tool": "get_revenue_drivers",
        "generated_from_row_count": 2,
        "emphasis_index": 1,
        "compact": compact,
    }


def build_time_series_chart(result: dict, *, force: bool = False) -> Optional[dict]:
    if result.get("suppress_chart") or result.get("_deep_dive_suppress_chart"):
        return None
    result = apply_sales_over_time_period_policy(result)
    series = result.get("series") or []
    if len(series) < 2:
        return None
    if not force and not result.get("_force_time_series"):
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
        description = f"{lookback_weeks} avslutade veckor fram till och med {end_label}"
        period_note = description
    else:
        title = "Försäljningsutveckling"
        description = f"Omsättning per {gran_label}"
        period_note = None
        if period_analysis.get("analysed_range_label"):
            period_note = period_analysis["analysed_range_label"]
        elif period_analysis.get("completed_week_label"):
            period_note = period_analysis["completed_week_label"]
        elif period_analysis.get("excluded_incomplete_period"):
            period_note = f"Pågående {gran_label} exkluderad från diagrammet."

    payload: dict = {
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
    highlights = _compute_highlights(data)
    if highlights:
        payload["highlights"] = highlights
    if is_relatively_flat_series(series):
        payload["stability_note"] = "Försäljningen var relativt stabil under perioden"
    return payload


def build_weekly_kpi_comparison_chart(result: dict) -> Optional[dict]:
    series = result.get("series") or []
    if len(series) < 2:
        return None
    prior_week = series[-2]
    current_week = series[-1]
    prior_rev = float(prior_week.get("revenue") or 0)
    curr_rev = float(current_week.get("revenue") or 0)
    if prior_rev <= 0 and curr_rev <= 0:
        return None
    rev_pct = round(100.0 * (curr_rev - prior_rev) / prior_rev, 1) if prior_rev > 0 else 0.0
    sign = "+" if rev_pct >= 0 else ""
    return {
        "chart_type": BAR_CHART,
        "chart_variant": "decline_comparison",
        "title": "Senaste avslutade veckan",
        "description": f"{sign}{rev_pct:.1f} % mot föregående vecka",
        "data": [
            {"period": "Föregående vecka", "revenue": round(prior_rev, 2)},
            {"period": "Senaste vecka", "revenue": round(curr_rev, 2)},
        ],
        "x_key": "period",
        "y_key": "revenue",
        "source_tool": "get_sales_over_time",
        "generated_from_row_count": 2,
        "emphasis_index": 1,
    }


def _build_sales_over_time(result: dict) -> Optional[dict]:
    return build_time_series_chart(result, force=bool(result.get("_force_time_series")))


def _build_supplier_kpis(result: dict) -> Optional[dict]:
    curr_rev = float(result.get("total_revenue") or 0)
    prior_rev = float(result.get("prev_total_revenue") or 0)
    if prior_rev <= 0 and curr_rev <= 0:
        return None
    rev_pct = round(100.0 * (curr_rev - prior_rev) / prior_rev, 1) if prior_rev > 0 else 0.0
    sign = "+" if rev_pct >= 0 else ""
    return {
        "chart_type": BAR_CHART,
        "chart_variant": "decline_comparison",
        "title": "Periodjämförelse",
        "description": f"{sign}{rev_pct:.1f} % omsättningsförändring",
        "data": [
            {"period": "Föregående period", "revenue": round(prior_rev, 2)},
            {"period": "Senaste period", "revenue": round(curr_rev, 2)},
        ],
        "x_key": "period",
        "y_key": "revenue",
        "source_tool": "get_supplier_kpis",
        "generated_from_row_count": 2,
        "emphasis_index": 1,
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
        {"name": "Vår andel", "revenue": round(sup_rev, 2)},
        {"name": "Övriga aktörer", "revenue": round(comp_rev, 2)},
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
    days = result.get("comparison_days", 30)
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
            "latest_period_revenue": p.get("latest_period_revenue"),
            "prior_period_revenue": p.get("prior_period_revenue"),
            "revenue_change": p.get("revenue_change"),
        })

    if len(data) == 0:
        return {
            "chart_type": "empty_state",
            "title": "Inga produkter i nedgång",
            "description": f"Alla produkter är stabila eller växer de senaste {days} dagarna.",
            "data": [],
            "x_key": "",
            "y_key": "",
            "source_tool": "get_declining_products",
            "generated_from_row_count": 0,
        }

    if result.get("_deep_dive_focus") == "portfolio" and len(data) >= 2:
        return {
            "chart_type": BAR_CHART,
            "layout": "horizontal",
            "title": "Produktjämförelse",
            "description": f"Omsättningsförändring % · senaste {days} dagar",
            "x_key": "display_label",
            "y_key": "revenue_change_pct",
            "tooltip_key": "product_name",
            "data": data,
            "source_tool": "get_declining_products",
            "generated_from_row_count": len(data),
            "emphasis_index": 0,
        }

    if result.get("_deep_dive_focus") == "product_trend":
        weekly = result.get("focus_product_weekly_series") or []
        if len(weekly) >= 2:
            trend_data = [
                {"label": p["period"], "revenue": p["revenue"]}
                for p in weekly
                if p.get("revenue") is not None
            ]
            if len(trend_data) >= 2:
                name = data[0]["product_name"] if data else "Produktutveckling"
                payload: dict = {
                    "chart_type": LINE_CHART,
                    "title": name,
                    "description": f"Veckovis omsättning · senaste {days} dagar",
                    "x_key": "label",
                    "y_key": "revenue",
                    "data": trend_data,
                    "source_tool": "get_declining_products",
                    "generated_from_row_count": len(trend_data),
                }
                highlights = _compute_highlights(trend_data)
                if highlights:
                    payload["highlights"] = highlights
                return payload

    if result.get("_deep_dive_focus") == "regions":
        regions = result.get("focus_product_regions") or []
        region_data = []
        for r in regions:
            change_pct = r.get("revenue_change_pct")
            if change_pct is None:
                continue
            region_data.append({
                "region": r["region"],
                "display_label": _truncate_label(r["region"]),
                "revenue_change_pct": change_pct,
            })
        if len(region_data) >= 2:
            return {
                "chart_type": BAR_CHART,
                "layout": "horizontal",
                "title": "Var syns tappet?",
                "description": f"Omsättningsförändring % per region · senaste {days} dagar",
                "x_key": "display_label",
                "y_key": "revenue_change_pct",
                "tooltip_key": "region",
                "data": region_data,
                "source_tool": "get_declining_products",
                "generated_from_row_count": len(region_data),
                "emphasis_index": 0,
            }

    if len(data) == 1:
        p = data[0]
        latest = p.get("latest_period_revenue") or 0.0
        prior = p.get("prior_period_revenue") or 0.0
        pct = abs(p.get("revenue_change_pct") or 0.0)
        name = p["product_name"]
        if prior > 0 or latest > 0:
            return {
                "chart_type": BAR_CHART,
                "chart_variant": "decline_comparison",
                "title": name,
                "description": f"−{pct:.0f} % omsättningsfall de senaste {days} dagarna",
                "data": [
                    {"period": "Föregående period", "revenue": round(prior, 2)},
                    {"period": "Senaste period", "revenue": round(latest, 2)},
                ],
                "x_key": "period",
                "y_key": "revenue",
                "source_tool": "get_declining_products",
                "generated_from_row_count": 1,
                "emphasis_index": 1,
            }
        return {
            "chart_type": "insight_card",
            "title": "Produkt i nedgång",
            "description": f"Tydligast nedgång de senaste {days} dagarna",
            "data": [p],
            "x_key": "product_name",
            "y_key": "revenue_change_pct",
            "source_tool": "get_declining_products",
            "generated_from_row_count": 1,
        }

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


def _build_revenue_drivers(result: dict) -> Optional[dict]:
    days = result.get("comparison_days", 30)
    focus = result.get("_deep_dive_focus")

    if focus == "gainers":
        items = result.get("gainers") or []
        data = [
            {
                "product_name": p["product_name"],
                "display_label": _truncate_label(p["product_name"]),
                "revenue_change": float(p.get("revenue_change") or 0),
            }
            for p in items
        ]
        if not data:
            return None
        return {
            "chart_type": BAR_CHART,
            "layout": "horizontal",
            "title": "Produkter som drev ökningen",
            "description": f"Absolut omsättningsökning · senaste {days} dagar",
            "x_key": "display_label",
            "y_key": "revenue_change",
            "tooltip_key": "product_name",
            "data": data,
            "source_tool": "get_revenue_drivers",
            "generated_from_row_count": len(data),
            "emphasis_index": 0,
        }

    if focus == "losers":
        items = result.get("losers") or []
        data = [
            {
                "product_name": p["product_name"],
                "display_label": _truncate_label(p["product_name"]),
                "revenue_change": float(p.get("revenue_change") or 0),
            }
            for p in items
        ]
        if not data:
            return None
        return {
            "chart_type": BAR_CHART,
            "layout": "horizontal",
            "title": "Produkter som tappade",
            "description": f"Absolut omsättningstapp · senaste {days} dagar",
            "x_key": "display_label",
            "y_key": "revenue_change",
            "tooltip_key": "product_name",
            "data": data,
            "source_tool": "get_revenue_drivers",
            "generated_from_row_count": len(data),
            "emphasis_index": 0,
        }

    if focus == "regions":
        gainers = result.get("region_gainers") or []
        losers = result.get("region_losers") or []
        combined = sorted(
            [*gainers, *losers],
            key=lambda r: abs(float(r.get("revenue_change") or 0)),
            reverse=True,
        )[:5]
        data = []
        for r in combined:
            change_pct = r.get("revenue_change_pct")
            if change_pct is None:
                prior = float(r.get("prior_period_revenue") or 0)
                curr = float(r.get("current_period_revenue") or 0)
                change_pct = round(100.0 * (curr - prior) / prior, 1) if prior > 0 else 0.0
            data.append({
                "region": r["region"],
                "display_label": _truncate_label(r["region"]),
                "revenue_change_pct": change_pct,
            })
        if len(data) < 2:
            return None
        return {
            "chart_type": BAR_CHART,
            "layout": "horizontal",
            "title": "Regional utveckling",
            "description": f"Omsättningsförändring % per region · senaste {days} dagar",
            "x_key": "display_label",
            "y_key": "revenue_change_pct",
            "tooltip_key": "region",
            "data": data,
            "source_tool": "get_revenue_drivers",
            "generated_from_row_count": len(data),
            "emphasis_index": 0,
        }

    if result.get("_chart_intent") == "period_comparison":
        return build_period_comparison_chart(result)

    return None


_BUILDERS = {
    "get_sales_over_time": _build_sales_over_time,
    "get_supplier_kpis": _build_supplier_kpis,
    "get_top_products": _build_top_products,
    "get_sales_by_region": _build_sales_by_region,
    "get_market_share": _build_market_share,
    "get_declining_products": _build_declining_products,
    "get_revenue_drivers": _build_revenue_drivers,
}


def build_chart(tool_name: str, result: dict) -> Optional[dict]:
    builder = _BUILDERS.get(tool_name)
    if builder is None:
        return None
    try:
        return builder(result)
    except (KeyError, TypeError, ValueError):
        return None


def pick_chart(tool_results: list[tuple[str, dict]], question: str = "") -> Optional[dict]:
    charts = pick_charts(tool_results, question)
    return charts[0] if charts else None


def pick_charts(tool_results: list[tuple[str, dict]], question: str = "") -> list[dict]:
    from app.services.chart_policy import select_charts
    return select_charts(question, tool_results)
