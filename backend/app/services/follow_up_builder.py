"""
Contextual follow-up chips grounded in verified tool output and supported routes.
"""

from __future__ import annotations

from app.services.comparison_labels import analyzed_period_label
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
        from datetime import date as dt
        s_d = dt.fromisoformat(start[:10])
        e_d = dt.fromisoformat(end[:10])
        if s_d.month == 1 and s_d.day == 1 and s_d.year == e_d.year:
            return "i år"
    except ValueError:
        pass
    label = analyzed_period_label(dr)
    return f"under perioden {label}"


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


def build_contextual_follow_ups(
    tool_results: list[tuple[str, dict]],
    question: str = "",
    deep_dive: dict | None = None,
) -> list[dict[str, str]]:
    """Merge deep-dive chips with overview, trend, ranking and market-share chips."""
    actions = build_follow_up_actions(deep_dive, question)
    if actions:
        return actions

    by_tool: dict[str, dict] = {}
    for name, result in tool_results:
        if isinstance(result, dict) and "error" not in result:
            by_tool[name] = result

    if "get_supplier_kpis" in by_tool and "get_sales_over_time" in by_tool:
        period = _period_phrase_from_range(by_tool["get_supplier_kpis"].get("date_range"), question)
        return [
            {
                "label": "Visa produkter som drev utvecklingen",
                "message": f"Vilka produkter drev utvecklingen {period}?",
            },
            {
                "label": "Visa utveckling per region",
                "message": f"Hur ser försäljningen ut per region {period}?",
            },
            {
                "label": "Jämför med samma period förra året",
                "message": f"Hur ser försäljningen ut jämfört med samma period förra året?",
            },
        ]

    if "get_market_share" in by_tool:
        ms = by_tool["get_market_share"]
        category = ms.get("category_name") or "kategorin"
        dr = ms.get("date_range") or {}
        span_phrase = _period_phrase_from_range(dr, question)
        chips = [
            {
                "label": f"Visa våra starkaste produkter inom {category}",
                "message": f"Vilka produkter säljer bäst inom {category} {span_phrase}?",
            },
            {
                "label": "Jämför med föregående 90 dagar",
                "message": f"Hur stor marknadsandel har vi inom {category} de senaste 90 dagarna?",
            },
        ]
        return chips

    if "get_top_products" in by_tool:
        products = by_tool["get_top_products"].get("products") or []
        period = _period_phrase_from_range(by_tool["get_top_products"].get("date_range"), question)
        region = by_tool["get_top_products"].get("region_filter")
        region_suffix = f" i {region}" if region else ""
        chips: list[dict[str, str]] = []
        if products:
            top = products[0].get("product_name")
            if top:
                chips.append({
                    "label": "Visa produktens utveckling över tid",
                    "message": f"Hur har {top} utvecklats {period}?",
                })
            if len(products) >= 2:
                a, b = products[0].get("product_name"), products[1].get("product_name")
                if a and b:
                    chips.append({
                        "label": "Jämför de två största produkterna",
                        "message": f"Jämför {a} och {b} {period}",
                    })
        chips.append({
            "label": "Visa försäljning per region",
            "message": f"Vilken region genererar mest intäkter{region_suffix} {period}?",
        })
        return chips[:3]

    if "get_sales_over_time" in by_tool and "get_revenue_drivers" not in by_tool:
        period = _period_phrase_from_range(by_tool["get_sales_over_time"].get("date_range"), question)
        if is_current_year_phrase(question) or "utveckl" in question.lower():
            return [
                {
                    "label": "Visa produkter som drev utvecklingen",
                    "message": f"Vilka produkter drev utvecklingen {period}?",
                },
                {
                    "label": "Visa utveckling per region",
                    "message": f"Hur ser försäljningen ut per region {period}?",
                },
            ]

    return []
