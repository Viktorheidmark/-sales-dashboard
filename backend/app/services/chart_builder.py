"""
Deterministic chart builder — converts raw MCP tool results into chart payloads.

Chart selection is governed by chart_policy.select_charts (intent-based).
"""

from datetime import date, timedelta
from typing import Optional

from app.services.comparison_labels import (
    kpi_comparison_label,
    market_share_period_label,
    revenue_drivers_comparison_label,
)
from app.services.decline_period import decline_trend_subtitle
from app.services.period_labels import append_chart_period, decline_comparison_period_label
from app.services.period_utils import (
    apply_sales_over_time_period_policy,
    format_compact_date_range_sv,
    format_date_sv,
    format_week_series_label_sv,
    week_bucket_bounds,
)

_MONTHS_SV = (
    "januari", "februari", "mars", "april", "maj", "juni",
    "juli", "augusti", "september", "oktober", "november", "december",
)

LINE_CHART = "line_chart"
BAR_CHART = "bar_chart"
PIE_CHART = "pie_chart"

_FLAT_REVENUE_PCT_THRESHOLD = 3.0
_FLAT_SERIES_CV_THRESHOLD = 0.05

_LABEL_MAX = 22


def _declining_product_rows(products: list[dict]) -> list[dict]:
    """Chart rows from the same products list used for narrative and deep dive."""
    rows: list[dict] = []
    for p in products:
        pct = p.get("revenue_change_pct")
        if pct is None:
            prior = float(p.get("prior_period_revenue") or 0)
            latest = float(p.get("latest_period_revenue") or 0)
            if prior > 0:
                pct = round(100.0 * (latest - prior) / prior, 2)
        if pct is None or pct >= 0:
            continue
        name = p["product_name"]
        latest = float(p.get("latest_period_revenue") or 0)
        prior = float(p.get("prior_period_revenue") or 0)
        change = p.get("revenue_change")
        if change is None:
            change = round(latest - prior, 2)
        rows.append({
            "product_name": name,
            "display_label": _truncate_label(name),
            "revenue_change_pct": pct,
            "latest_period_revenue": latest,
            "prior_period_revenue": prior,
            "revenue_change": change,
        })
    rows.sort(key=lambda r: float(r.get("revenue_change") or 0))
    return rows


def _decline_chart_description(result: dict) -> str:
    label = result.get("comparison_period_label") or decline_comparison_period_label(result)
    return label


def build_decline_trend_chart(result: dict) -> Optional[dict]:
    """Primary decline visualization — weekly revenue trend with period split."""
    products = result.get("products") or []
    if not products:
        return None
    focus = products[0]
    weekly = result.get("focus_product_weekly_series") or []
    if len(weekly) < 2:
        return None

    latest_period = result.get("latest_period") or {}
    prior_period = result.get("prior_period") or {}
    split_at = latest_period.get("start")
    name = focus["product_name"]

    data: list[dict] = []
    for point in weekly:
        period = str(point.get("period") or "")
        axis_label, tooltip_label = _series_row_label(period, "week")
        phase = "latest"
        if split_at and period < split_at:
            phase = "prior"
        data.append({
            "label": period,
            "display_label": axis_label,
            "tooltip_label": tooltip_label,
            "revenue": float(point.get("revenue") or 0),
            "period_phase": phase,
        })

    rev_change = focus.get("revenue_change")
    if rev_change is None:
        rev_change = round(
            float(focus.get("latest_period_revenue") or 0) - float(focus.get("prior_period_revenue") or 0),
            2,
        )

    prior_label = "Föregående period"
    latest_label = "Senaste period"
    if prior_period.get("start") and prior_period.get("end"):
        prior_label = format_compact_date_range_sv(prior_period["start"], prior_period["end"])
    if latest_period.get("start") and latest_period.get("end"):
        latest_label = format_compact_date_range_sv(latest_period["start"], latest_period["end"])

    return {
        "chart_type": LINE_CHART,
        "chart_variant": "decline_trend",
        "title": f"Utveckling för {name}",
        "description": decline_trend_subtitle(result),
        "x_key": "display_label",
        "y_key": "revenue",
        "tooltip_key": "tooltip_label",
        "data": data,
        "source_tool": "get_declining_products",
        "generated_from_row_count": len(data),
        "period_split_at": split_at,
        "period_split_label": "Senaste period",
        "prior_period_label": prior_label,
        "latest_period_label": latest_label,
        "decline_metrics": {
            "prior_revenue": focus.get("prior_period_revenue"),
            "latest_revenue": focus.get("latest_period_revenue"),
            "revenue_change": rev_change,
            "revenue_change_pct": focus.get("revenue_change_pct"),
        },
        "show_markers": True,
        "y_axis_from_zero": True,
        "trend_granularity": "week",
    }


def build_decline_ranking_chart(result: dict) -> Optional[dict]:
    """Secondary decline ranking — sorted by absolute SEK decline."""
    products = result.get("products") or []
    rows = _declining_product_rows(products)
    if not rows:
        return None
    data = [
        {
            "product_name": row["product_name"],
            "display_label": row["display_label"],
            "revenue_change": float(row.get("revenue_change") or 0),
            "revenue_change_pct": row.get("revenue_change_pct"),
        }
        for row in rows
    ]
    title = "Andra produkter i nedgång" if len(data) > 1 else "Produkter i nedgång"
    return {
        "chart_type": BAR_CHART,
        "chart_variant": "decline_ranking",
        "layout": "horizontal",
        "title": title,
        "description": _decline_chart_description(result),
        "x_key": "display_label",
        "y_key": "revenue_change",
        "tooltip_key": "product_name",
        "data": data,
        "source_tool": "get_declining_products",
        "generated_from_row_count": len(data),
        "emphasis_index": 0,
        "compact": True,
    }


def _truncate_label(text: str, max_len: int = _LABEL_MAX) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _shorten_period(period: str, granularity: str) -> str:
    if granularity == "month" and len(period) == 10:
        return period[:7]
    return period


def _month_axis_label(period: str) -> str:
    """Compact month label for chart axis, e.g. 'maj 26'."""
    try:
        d = date.fromisoformat(period[:7] + "-01") if len(period) >= 7 else date.fromisoformat(period[:10])
        return f"{_MONTHS_SV[d.month - 1][:3]} {str(d.year)[-2:]}"
    except ValueError:
        return period[:7] if len(period) >= 7 else period


def _month_tooltip_label(period: str) -> str:
    try:
        d = date.fromisoformat(period[:7] + "-01") if len(period) >= 7 else date.fromisoformat(period[:10])
        return f"{_MONTHS_SV[d.month - 1].capitalize()} {d.year}"
    except ValueError:
        return period


def _series_row_label(
    period: str,
    granularity: str,
    query_start: Optional[str] = None,
) -> tuple[str, str]:
    """Return (axis_label, tooltip_label)."""
    if granularity == "month":
        return _month_axis_label(period), _month_tooltip_label(period)
    if granularity == "week" and len(period) >= 10:
        start, end = week_bucket_bounds(period[:10], query_start)
        axis = format_compact_date_range_sv(start, end)
        tip = format_week_series_label_sv(period[:10], query_start)
        return axis, tip
    return _shorten_period(period, granularity), period


def _query_start_from_result(result: dict) -> Optional[str]:
    qdr = result.get("query_date_range") or {}
    return (
        qdr.get("requested_start")
        or qdr.get("start")
        or (result.get("date_range") or {}).get("start")
    )


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


def _granularity_label(granularity: str) -> str:
    return {"day": "dag", "week": "vecka", "month": "månad"}.get(granularity, granularity)


def _compute_highlights(data: list[dict], *, granularity: str = "month") -> Optional[dict]:
    if len(data) < 2:
        return None
    valid = []
    for row in data:
        if row.get("revenue") is None:
            continue
        axis_lbl = row["label"]
        display_lbl = row.get("display_label") or axis_lbl
        valid.append((axis_lbl, display_lbl, float(row["revenue"])))
    if len(valid) < 2:
        return None

    peak_axis, peak_display, peak_rev = max(valid, key=lambda x: x[2])
    trough_axis, trough_display, trough_rev = min(valid, key=lambda x: x[2])
    if granularity == "week":
        peak_display = peak_axis
        trough_display = trough_axis
    first_rev = valid[0][2]
    last_rev = valid[-1][2]
    avg_rev = sum(r for _, _, r in valid) / len(valid)
    change_pct = round((last_rev - first_rev) / first_rev * 100, 1) if first_rev > 0 else 0.0

    return {
        "peak_label": peak_axis,
        "peak_revenue": round(peak_rev, 2),
        "peak_label_display": peak_display,
        "trough_label": trough_axis,
        "trough_revenue": round(trough_rev, 2),
        "trough_label_display": trough_display,
        "first_revenue": round(first_rev, 2),
        "last_revenue": round(last_rev, 2),
        "avg_revenue": round(avg_rev, 2),
        "change_pct": change_pct,
        "granularity": granularity,
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
    # Bug 2: never render a comparison chart when the baseline is empty/zero —
    # it produces a broken single-bar chart. Caller should fall back to time series.
    if prior_rev <= 0:
        return None
    rev_pct = round(100.0 * (curr_rev - prior_rev) / prior_rev, 1)
    sign = "+" if rev_pct >= 0 else ""
    comp_label = revenue_drivers_comparison_label(result)
    title = "Periodjämförelse" if not compact else comp_label.capitalize()
    return {
        "chart_type": BAR_CHART,
        "chart_variant": "decline_comparison",
        "title": title,
        "description": f"{sign}{rev_pct:.1f} % omsättningsförändring · {comp_label}",
        "data": [
            {"period": "Jämförelseperiod", "revenue": round(prior_rev, 2)},
            {"period": "Analyserad period", "revenue": round(curr_rev, 2)},
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
    query_start = _query_start_from_result(result)
    data = []
    for p in series:
        if p.get("revenue") is None:
            continue
        period = str(p["period"])
        if p.get("period_label") and granularity == "week":
            axis_lbl = format_compact_date_range_sv(*week_bucket_bounds(period[:10], query_start))
            tip_lbl = p["period_label"]
        else:
            axis_lbl, tip_lbl = _series_row_label(period, granularity, query_start)
        row = {
            "label": axis_lbl,
            "display_label": tip_lbl,
            "revenue": p["revenue"],
        }
        if p.get("orders") is not None:
            row["orders"] = p["orders"]
        data.append(row)
    if len(data) < 2:
        return None

    chart_context = result.get("chart_context") or {}
    period_analysis = result.get("period_analysis") or {}
    widened = chart_context.get("widened")
    lookback_weeks = chart_context.get("lookback_weeks", 8)

    if widened and granularity == "week":
        orig = chart_context.get("original_date_range") or {}
        week_end = orig.get("end") or (result.get("date_range") or {}).get("end")
        if not week_end and series:
            last_period = str(series[-1].get("period", ""))[:10]
            last_monday = date.fromisoformat(last_period)
            week_end = (last_monday + timedelta(days=6)).isoformat()
        title = "Utveckling inför senaste avslutade vecka"
        end_label = format_date_sv(week_end) if week_end else "senaste avslutade vecka"
        description = f"{lookback_weeks} avslutade veckor fram till och med {end_label}"
        period_note = description
    else:
        title = "Försäljningsutveckling"
        description = append_chart_period(f"Omsättning per {gran_label}", result)
        period_note = None
        if period_analysis.get("analysed_range_label"):
            period_note = period_analysis["analysed_range_label"]
        elif period_analysis.get("completed_week_label"):
            period_note = period_analysis["completed_week_label"]
        elif period_analysis.get("excluded_incomplete_period"):
            if granularity == "month":
                period_note = "Pågående månad exkluderad — diagrammet visar fullständiga månader."
            else:
                period_note = f"Pågående {gran_label} exkluderad från diagrammet."

    payload: dict = {
        "chart_type": LINE_CHART,
        "title": title,
        "description": description,
        "x_key": "label",
        "y_key": "revenue",
        "tooltip_key": "display_label",
        "data": data,
        "source_tool": "get_sales_over_time",
        "generated_from_row_count": len(data),
        "period_note": period_note,
        "show_markers": granularity in ("month", "week"),
        "y_axis_from_zero": True,
        "trend_granularity": granularity,
    }
    highlights = _compute_highlights(data, granularity=granularity)
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
    prior_rev_raw = result.get("prev_total_revenue")
    if prior_rev_raw is None:
        return None
    prior_rev = float(prior_rev_raw)
    # Empty prior window (COALESCE → 0) produces a broken single-bar chart — skip it.
    if prior_rev <= 0:
        return None
    rev_pct = round(100.0 * (curr_rev - prior_rev) / prior_rev, 1)
    sign = "+" if rev_pct >= 0 else ""
    comp_label = kpi_comparison_label(result)
    payload = {
        "chart_type": BAR_CHART,
        "chart_variant": "decline_comparison",
        "title": "Periodjämförelse",
        "description": f"{sign}{rev_pct:.1f} % omsättningsförändring · {comp_label}",
        "data": [
            {"period": "Jämförelseperiod", "revenue": round(prior_rev, 2)},
            {"period": "Analyserad period", "revenue": round(curr_rev, 2)},
        ],
        "x_key": "period",
        "y_key": "revenue",
        "source_tool": "get_supplier_kpis",
        "generated_from_row_count": 2,
        "emphasis_index": 1,
    }
    payload["description"] = append_chart_period(payload["description"], result)
    return payload


def _build_top_products(result: dict) -> Optional[dict]:
    products = result.get("products") or []
    requested = result.get("requested_limit")
    if requested is not None:
        products = products[: int(requested)]
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
    base = f"Omsättning per produkt · {region}" if region else "Omsättning per produkt"
    subtitle = append_chart_period(base, result)

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
        "description": append_chart_period("Omsättning per region", result),
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
        "description": market_share_period_label(result),
        "x_key": "name",
        "y_key": "revenue",
        "data": data,
        "source_tool": "get_market_share",
        "generated_from_row_count": 2,
    }


def _build_declining_products(result: dict) -> Optional[dict]:
    products = result.get("products") or []
    data = _declining_product_rows(products)
    period_desc = _decline_chart_description(result)

    if len(products) == 0 or len(data) == 0:
        return {
            "chart_type": "empty_state",
            "title": "Inga produkter i nedgång",
            "description": (
                f"Inga produkter har negativ omsättningsförändring i vald jämförelse. "
                f"{period_desc}"
            ),
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
            "title": "Produkter i nedgång",
            "description": period_desc,
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
        days = result.get("comparison_days", 30)
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
                    "description": period_desc,
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
            if change_pct is None or change_pct >= 0:
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
                "description": period_desc,
                "x_key": "display_label",
                "y_key": "revenue_change_pct",
                "tooltip_key": "region",
                "data": region_data,
                "source_tool": "get_declining_products",
                "generated_from_row_count": len(region_data),
                "emphasis_index": 0,
            }

    if len(data) == 1:
        trend = build_decline_trend_chart(result)
        if trend:
            return trend
        p = data[0]
        latest = p.get("latest_period_revenue") or 0.0
        prior = p.get("prior_period_revenue") or 0.0
        pct = abs(p.get("revenue_change_pct") or 0.0)
        name = p["product_name"]
        prior_label = "Föregående period"
        latest_label = "Senaste period"
        prior_period = result.get("prior_period") or {}
        latest_period = result.get("latest_period") or {}
        if prior_period.get("start") and prior_period.get("end"):
            prior_label = format_compact_date_range_sv(prior_period["start"], prior_period["end"])
        if latest_period.get("start") and latest_period.get("end"):
            latest_label = format_compact_date_range_sv(latest_period["start"], latest_period["end"])
        if prior > 0 or latest > 0:
            return {
                "chart_type": BAR_CHART,
                "chart_variant": "decline_comparison",
                "title": "Produkter i nedgång",
                "description": f"{name} · −{pct:.1f} % · {period_desc}",
                "data": [
                    {"period": prior_label, "revenue": round(prior, 2)},
                    {"period": latest_label, "revenue": round(latest, 2)},
                ],
                "x_key": "period",
                "y_key": "revenue",
                "source_tool": "get_declining_products",
                "generated_from_row_count": 1,
                "emphasis_index": 1,
            }
        return {
            "chart_type": "insight_card",
            "title": "Produkter i nedgång",
            "description": f"{name} · −{pct:.1f} % · {period_desc}",
            "data": [p],
            "x_key": "product_name",
            "y_key": "revenue_change_pct",
            "source_tool": "get_declining_products",
            "generated_from_row_count": 1,
        }

    trend = build_decline_trend_chart(result)
    if trend:
        return trend

    return {
        "chart_type": BAR_CHART,
        "layout": "horizontal",
        "title": "Produkter i nedgång",
        "description": period_desc,
        "x_key": "display_label",
        "y_key": "revenue_change",
        "tooltip_key": "product_name",
        "data": [
            {
                "product_name": row["product_name"],
                "display_label": row["display_label"],
                "revenue_change": float(row.get("revenue_change") or 0),
                "revenue_change_pct": row.get("revenue_change_pct"),
            }
            for row in data
        ],
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
