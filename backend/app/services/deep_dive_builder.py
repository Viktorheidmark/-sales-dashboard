"""
Deterministic deep-dive payloads for supplier-scoped period comparisons.

Built only from validated MCP tool output — never from LLM text.
"""

from __future__ import annotations

from typing import Any, Optional

_FLAT_REVENUE_PCT_THRESHOLD = 3.0
_FLAT_SERIES_CV_THRESHOLD = 0.05


def _pct_change(current: float, prior: float) -> Optional[float]:
    if prior <= 0:
        return None
    return round(100.0 * (current - prior) / prior, 1)


def _driver_row(
    *,
    rank: int,
    label: str,
    current: float,
    prior: float,
    label_key: str = "label",
) -> dict:
    change = round(current - prior, 2)
    return {
        "rank": rank,
        label_key: label,
        "current_period_revenue": round(current, 2),
        "prior_period_revenue": round(prior, 2),
        "revenue_change": change,
        "revenue_change_pct": _pct_change(current, prior),
    }


def _is_meaningful_series(series: list[dict]) -> bool:
    revs = [float(p.get("revenue") or 0) for p in series if p.get("revenue") is not None]
    if len(revs) < 3:
        return False
    mean = sum(revs) / len(revs)
    if mean <= 0:
        return False
    spread = max(revs) - min(revs)
    if spread / mean < _FLAT_SERIES_CV_THRESHOLD:
        return False
    first, last = revs[0], revs[-1]
    if first > 0 and abs((last - first) / first * 100) < _FLAT_REVENUE_PCT_THRESHOLD:
        return spread / mean < _FLAT_SERIES_CV_THRESHOLD * 2
    return True


def _period_block(block: dict) -> dict:
    return {
        "start": block.get("start"),
        "end": block.get("end"),
        "total_revenue": block.get("total_revenue", 0.0),
        "total_orders": block.get("total_orders", 0),
        "total_units": block.get("total_units", 0),
    }


def _build_revenue_development(
    drivers: dict,
    sales_series: Optional[list[dict]] = None,
) -> dict:
    days = drivers.get("comparison_days", 30)
    current = drivers.get("current_period") or {}
    prior = drivers.get("prior_period") or {}
    curr_rev = float(current.get("total_revenue") or 0)
    prior_rev = float(prior.get("total_revenue") or 0)
    curr_orders = int(current.get("total_orders") or 0)
    prior_orders = int(prior.get("total_orders") or 0)
    curr_units = int(current.get("total_units") or 0)
    prior_units = int(prior.get("total_units") or 0)

    gainers = [
        _driver_row(
            rank=p.get("rank", i + 1),
            label=p["product_name"],
            current=float(p.get("current_period_revenue") or 0),
            prior=float(p.get("prior_period_revenue") or 0),
            label_key="product_name",
        )
        for i, p in enumerate(drivers.get("gainers") or [])
    ]
    losers = [
        _driver_row(
            rank=p.get("rank", i + 1),
            label=p["product_name"],
            current=float(p.get("current_period_revenue") or 0),
            prior=float(p.get("prior_period_revenue") or 0),
            label_key="product_name",
        )
        for i, p in enumerate(drivers.get("losers") or [])
    ]

    reg_gainers = drivers.get("region_gainers") or []
    reg_losers = drivers.get("region_losers") or []
    strongest = None
    weakest = None
    if reg_gainers:
        r = reg_gainers[0]
        strongest = _driver_row(
            rank=r.get("rank", 1),
            label=r["region"],
            current=float(r.get("current_period_revenue") or 0),
            prior=float(r.get("prior_period_revenue") or 0),
            label_key="region",
        )
    if reg_losers:
        r = reg_losers[0]
        weakest = _driver_row(
            rank=r.get("rank", 1),
            label=r["region"],
            current=float(r.get("current_period_revenue") or 0),
            prior=float(r.get("prior_period_revenue") or 0),
            label_key="region",
        )

    rev_pct = _pct_change(curr_rev, prior_rev)
    relatively_stable = rev_pct is not None and abs(rev_pct) < _FLAT_REVENUE_PCT_THRESHOLD

    return {
        "kind": "revenue_development",
        "comparison_days": days,
        "period_summary": {
            "current": _period_block(current),
            "prior": _period_block(prior),
            "revenue_change": round(curr_rev - prior_rev, 2),
            "revenue_change_pct": rev_pct,
            "orders_change": curr_orders - prior_orders,
            "units_change": curr_units - prior_units,
        },
        "top_gainers": gainers,
        "top_losers": losers,
        "strongest_region": strongest,
        "weakest_region": weakest,
        "relatively_stable": relatively_stable,
    }


def _build_product_decline(declining: dict) -> Optional[dict]:
    products = declining.get("products") or []
    if not products:
        return {
            "kind": "product_decline",
            "comparison_days": declining.get("comparison_days", 30),
            "period_summary": None,
            "focus_product": None,
            "portfolio_comparison": [],
        }

    focus = products[0]
    days = declining.get("comparison_days", 30)
    latest_rev = float(focus.get("latest_period_revenue") or 0)
    prior_rev = float(focus.get("prior_period_revenue") or 0)
    latest_orders = int(focus.get("latest_period_orders") or 0)
    prior_orders = int(focus.get("prior_period_orders") or 0)
    latest_units = int(focus.get("latest_period_units") or 0)
    prior_units = int(focus.get("prior_period_units") or 0)

    regions = [
        _driver_row(
            rank=r.get("rank", i + 1),
            label=r["region"],
            current=float(r.get("current_period_revenue") or 0),
            prior=float(r.get("prior_period_revenue") or 0),
            label_key="region",
        )
        for i, r in enumerate(declining.get("focus_product_regions") or [])
    ]

    portfolio = [
        _driver_row(
            rank=p.get("rank", i + 1),
            label=p["product_name"],
            current=float(p.get("latest_period_revenue") or 0),
            prior=float(p.get("prior_period_revenue") or 0),
            label_key="product_name",
        )
        for i, p in enumerate(products[:5])
    ]

    weekly = declining.get("focus_product_weekly_series") or []
    rev_pct = focus.get("revenue_change_pct")
    if rev_pct is None:
        rev_pct = _pct_change(latest_rev, prior_rev)

    return {
        "kind": "product_decline",
        "comparison_days": days,
        "period_summary": {
            "current": {
                "start": (declining.get("latest_period") or {}).get("start"),
                "end": (declining.get("latest_period") or {}).get("end"),
                "total_revenue": round(latest_rev, 2),
                "total_orders": latest_orders,
                "total_units": latest_units,
            },
            "prior": {
                "start": (declining.get("prior_period") or {}).get("start"),
                "end": (declining.get("prior_period") or {}).get("end"),
                "total_revenue": round(prior_rev, 2),
                "total_orders": prior_orders,
                "total_units": prior_units,
            },
            "revenue_change": round(latest_rev - prior_rev, 2),
            "revenue_change_pct": rev_pct,
            "orders_change": latest_orders - prior_orders,
            "units_change": latest_units - prior_units,
        },
        "focus_product": {
            "product_name": focus["product_name"],
            "sku": focus.get("sku"),
            "top_regions": regions,
        },
        "portfolio_comparison": portfolio,
    }


def build_deep_dive(tool_results: list[tuple[str, dict]]) -> Optional[dict]:
    by_tool: dict[str, dict] = {}
    for name, result in tool_results:
        if isinstance(result, dict) and "error" not in result:
            by_tool[name] = result

    if "get_revenue_drivers" in by_tool:
        sales_series = None
        if "get_sales_over_time" in by_tool:
            sales_series = by_tool["get_sales_over_time"].get("series")
        return _build_revenue_development(by_tool["get_revenue_drivers"], sales_series)

    if "get_declining_products" in by_tool:
        declining = by_tool["get_declining_products"]
        if declining.get("_deep_dive_focus") == "portfolio":
            return None
        return _build_product_decline(declining)

    return None


def build_follow_up_actions(
    deep_dive: Optional[dict],
    question: str = "",
) -> list[dict[str, str]]:
    if not deep_dive:
        return []

    days = deep_dive.get("comparison_days", 30)
    period = f"de senaste {days} dagarna"
    kind = deep_dive.get("kind")

    if kind == "revenue_development":
        actions = [
            {"label": "Visa produkter som drev ökningen", "message": f"Visa produkter som drev ökningen {period}"},
            {"label": "Visa produkter som tappade", "message": f"Visa produkter som tappade {period}"},
            {"label": "Visa utveckling per region", "message": f"Visa utveckling per region {period}"},
        ]
        if deep_dive.get("relatively_stable"):
            actions.append({"label": "Visa trend över tid", "message": f"Visa försäljningstrend {period}"})
        return actions

    if kind == "product_decline":
        focus = (deep_dive.get("focus_product") or {}).get("product_name")
        if not focus:
            return []
        return [
            {"label": "Visa tappet per region", "message": f"Visa tappet per region för {focus} {period}"},
            {"label": "Visa produktens utveckling över tid", "message": f"Visa {focus}s utveckling över tid {period}"},
            {"label": "Jämför med övriga produkter", "message": f"Jämför {focus} med övriga produkter {period}"},
        ]

    return []
