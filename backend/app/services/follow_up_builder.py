"""
Contextual follow-up chips grounded in verified tool output and supported routes.
"""

from __future__ import annotations

from app.services.comparison_labels import analyzed_period_label
from app.services.follow_up_context import extract_analysis_context, make_follow_up_action
from app.services.period_utils import is_current_year_phrase


def _period_phrase_from_range(date_range: dict | None, question: str = "") -> str:
    if is_current_year_phrase(question):
        return "i år"
    if not date_range or not date_range.get("start"):
        return "under samma period"
    dr = date_range
    start, end = dr.get("start", ""), dr.get("end", "")
    from datetime import date as dt

    try:
        span = (dt.fromisoformat(end[:10]) - dt.fromisoformat(start[:10])).days + 1
    except ValueError:
        span = 0
    if span == 30:
        return "de senaste 30 dagarna"
    if span == 90:
        return "de senaste 90 dagarna"
    try:
        s_d = dt.fromisoformat(start[:10])
        e_d = dt.fromisoformat(end[:10])
        if s_d.month == 1 and s_d.day == 1 and s_d.year == e_d.year:
            return "i år"
    except ValueError:
        pass
    label = analyzed_period_label(dr)
    return f"under perioden {label}"


def _ctx_from_results(
    tool_results: list[tuple[str, dict]],
    question: str,
) -> dict:
    return extract_analysis_context(tool_results, question)


def _decline_follow_ups(product_name: str, period: str) -> list[dict[str, str]]:
    return [
        {
            "label": "Visa tappet per region",
            "message": f"Visa tappet per region för {product_name} {period}",
        },
        {
            "label": "Visa produktens utveckling över tid",
            "message": f"Visa {product_name}s utveckling över tid {period}",
        },
        {
            "label": "Jämför med övriga produkter",
            "message": f"Jämför {product_name} med övriga produkter {period}",
        },
    ]


def build_follow_up_actions(
    deep_dive: dict | None,
    question: str = "",
) -> list[dict[str, str]]:
    """Deep-dive specific follow-ups (revenue drivers, product decline)."""
    if not deep_dive:
        return []

    days = deep_dive.get("comparison_days", 30)
    period = f"de senaste {days} dagarna"
    kind = deep_dive.get("kind")

    if kind == "revenue_development":
        actions = [
            {
                "label": "Visa vilka produkter som driver utvecklingen",
                "message": f"Vilka produkter drev utvecklingen {period}?",
            },
            {
                "label": "Visa produkter som tappade",
                "message": f"Vilka produkter tappade {period}?",
            },
            make_follow_up_action(
                "Visa utveckling per region",
                f"Hur ser försäljningen ut per region {period}?",
                "region_breakdown",
                _ctx_from_results([], question),
            ),
        ]
        return actions[:3]

    if kind == "product_decline":
        focus = (deep_dive.get("focus_product") or {}).get("product_name")
        if not focus:
            return []
        return _decline_follow_ups(focus, period)

    return []


def build_contextual_follow_ups(
    tool_results: list[tuple[str, dict]],
    question: str = "",
    deep_dive: dict | None = None,
) -> list[dict[str, str]]:
    """Merge deep-dive chips with overview, trend, ranking and market-share chips."""
    actions = build_follow_up_actions(deep_dive, question)
    if actions:
        return actions[:3]

    by_tool: dict[str, dict] = {}
    for name, result in tool_results:
        if isinstance(result, dict) and "error" not in result:
            by_tool[name] = result

    ctx = _ctx_from_results(tool_results, question)

    if "get_market_share" in by_tool:
        ms = by_tool["get_market_share"]
        category = ms.get("category_name") or "kategorin"
        dr = ms.get("date_range") or {}
        span_phrase = _period_phrase_from_range(dr, question)
        return [
            {
                "label": f"Visa våra starkaste produkter inom {category}",
                "message": f"Vilka produkter säljer bäst inom {category} {span_phrase}?",
            },
            {
                "label": "Visa marknadsandel över tid",
                "message": f"Hur har marknadsandelen inom {category} utvecklats {span_phrase}?",
            },
            make_follow_up_action(
                "Visa försäljning per region",
                f"Hur ser försäljningen ut per region {span_phrase}?",
                "region_breakdown",
                ctx,
            ),
        ][:3]

    if "get_declining_products" in by_tool:
        decl = by_tool["get_declining_products"]
        days = int(decl.get("comparison_days") or 30)
        period = f"de senaste {days} dagarna"
        products = decl.get("products") or []
        focus = products[0].get("product_name") if products else None
        if focus:
            return _decline_follow_ups(focus, period)

    if "get_top_products" in by_tool:
        products = by_tool["get_top_products"].get("products") or []
        period = _period_phrase_from_range(by_tool["get_top_products"].get("date_range"), question)
        region = by_tool["get_top_products"].get("region_filter")
        region_suffix = f" i {region}" if region else ""
        chips: list[dict[str, str]] = []
        if products:
            top = products[0].get("product_name")
            if top:
                chips.append(make_follow_up_action(
                    "Visa produktens utveckling över tid",
                    f"Hur har {top} utvecklats {period}?",
                    "product_trend",
                    ctx,
                ))
            if len(products) >= 2:
                a, b = products[0].get("product_name"), products[1].get("product_name")
                if a and b:
                    chips.append({
                        "label": "Jämför de två största produkterna",
                        "message": f"Jämför {a} och {b} {period}",
                    })
        chips.append(make_follow_up_action(
            "Visa försäljning per region",
            f"Vilken region genererar mest intäkter{region_suffix} {period}?",
            "region_breakdown",
            ctx,
        ))
        return chips[:3]

    if "get_sales_by_region" in by_tool:
        period = _period_phrase_from_range(by_tool["get_sales_by_region"].get("date_range"), question)
        regions = by_tool["get_sales_by_region"].get("regions") or []
        top_region = regions[0].get("region") if regions else None
        chips: list[dict[str, str]] = []
        if top_region:
            chips.append({
                "label": f"Visa starkaste produkter i {top_region}",
                "message": f"Vilka produkter säljer bäst i {top_region} {period}?",
            })
        chips.append({
            "label": "Jämför med andra regioner",
            "message": f"Hur ser försäljningen ut per region {period}?",
        })
        chips.append(make_follow_up_action(
            "Visa utveckling över tid",
            f"Hur har försäljningen utvecklats {period}?",
            "weekly_trend",
            ctx,
        ))
        return chips[:3]

    if "get_supplier_kpis" in by_tool and "get_sales_over_time" in by_tool:
        period = _period_phrase_from_range(by_tool["get_supplier_kpis"].get("date_range"), question)
        return [
            make_follow_up_action(
                "Visa utveckling per vecka",
                f"Visa utveckling per vecka {period}",
                "weekly_trend",
                ctx,
            ),
            make_follow_up_action(
                "Visa vilka produkter som driver utvecklingen",
                f"Vilka produkter drev utvecklingen {period}?",
                "product_drivers",
                ctx,
            ),
            make_follow_up_action(
                "Visa utveckling per region",
                f"Hur ser försäljningen ut per region {period}?",
                "region_breakdown",
                ctx,
            ),
        ][:3]

    if "get_sales_over_time" in by_tool and "get_revenue_drivers" not in by_tool:
        period = _period_phrase_from_range(by_tool["get_sales_over_time"].get("date_range"), question)
        sales = by_tool["get_sales_over_time"]
        actions: list[dict[str, str]] = []
        if sales.get("granularity", "month") == "month":
            actions.append(make_follow_up_action(
                "Visa utveckling per vecka",
                f"Visa utveckling per vecka {period}",
                "weekly_trend",
                ctx,
            ))
        actions.extend([
            make_follow_up_action(
                "Visa vilka produkter som driver utvecklingen",
                f"Vilka produkter drev utvecklingen {period}?",
                "product_drivers",
                ctx,
            ),
            make_follow_up_action(
                "Visa utveckling per region",
                f"Hur ser försäljningen ut per region {period}?",
                "region_breakdown",
                ctx,
            ),
        ])
        return actions[:3]

    return []
