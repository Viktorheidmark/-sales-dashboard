"""
Deterministic Swedish labels for analyzed periods and comparison baselines.

Derived only from verified MCP tool payloads — never from LLM text.
"""

from __future__ import annotations

from datetime import date

from app.services.period_utils import format_date_range_sv
from app.services.period_labels import (
    answer_period_phrase,
    chart_period_suffix,
    decline_comparison_period_label,
    infer_period_kind,
)


def _parse(d: str | None) -> date | None:
    if not d:
        return None
    try:
        return date.fromisoformat(str(d)[:10])
    except ValueError:
        return None


def _period_days(start: str, end: str) -> int:
    s, e = _parse(start), _parse(end)
    if not s or not e:
        return 0
    return (e - s).days + 1


def analyzed_period_label(date_range: dict | None, *, prefix: str = "", message: str = "") -> str:
    """Human-readable label for the primary analyzed window."""
    kind = infer_period_kind(date_range, message=message)
    phrase = answer_period_phrase(kind, date_range, message)
    if kind in ("year_to_date", "current_year"):
        start, end = (date_range or {}).get("start"), (date_range or {}).get("end")
        if start and end:
            return f"hittills i år ({format_date_range_sv(start, end)})"
    if kind in ("ui_default", "safe_fallback", "rolling_90", "rolling_quarter"):
        start, end = (date_range or {}).get("start"), (date_range or {}).get("end")
        if start and end:
            return f"{phrase} ({format_date_range_sv(start, end)})"
    if kind in ("ui_default_30", "rolling_30"):
        start, end = (date_range or {}).get("start"), (date_range or {}).get("end")
        if start and end:
            return f"{phrase} ({format_date_range_sv(start, end)})"
    body = phrase if phrase else format_date_range_sv(
        (date_range or {}).get("start", ""),
        (date_range or {}).get("end", ""),
    )
    return f"{prefix}{body}".strip() if prefix else body


def market_share_period_label(result: dict, message: str = "") -> str:
    category = result.get("category_name") or "kategorin"
    dr = result.get("date_range") or {}
    kind = result.get("_period_kind") or infer_period_kind(dr, message=message)
    suffix = chart_period_suffix(kind, dr, message)
    return f"Marknadsandel inom {category} · {suffix}"


def kpi_comparison_label(result: dict) -> str:
    """Label for get_supplier_kpis comparison baseline."""
    prev = result.get("prev_date_range") or {}
    curr = result.get("date_range") or {}
    if not prev.get("start") or not prev.get("end"):
        days = _period_days(curr.get("start", ""), curr.get("end", ""))
        return f"jämfört med föregående {days} dagarna" if days else "jämfört med föregående period"

    prev_start, prev_end = prev["start"], prev["end"]
    kind = result.get("comparison_kind")

    if kind == "year_over_year" or _is_yoy_kpi_comparison(result):
        return (
            f"jämfört med samma period föregående år, "
            f"{format_date_range_sv(prev_start, prev_end)}"
        )

    days = _period_days(curr.get("start", ""), curr.get("end", ""))
    ps, pe = _parse(prev_start), _parse(prev_end)

    if days == 7:
        return "jämfört med föregående avslutade vecka"

    if days == 30:
        return "jämfört med föregående 30 dagarna"

    if days > 0:
        return (
            f"jämfört med föregående {days} dagarna "
            f"({format_date_range_sv(prev_start, prev_end)})"
        )
    return f"jämfört med perioden {format_date_range_sv(prev_start, prev_end)}"


def _is_yoy_kpi_comparison(result: dict) -> bool:
    """Detect YoY KPI comparison from date ranges when comparison_kind is absent."""
    curr = result.get("date_range") or {}
    prev = result.get("prev_date_range") or {}
    cs, ce = _parse(curr.get("start")), _parse(curr.get("end"))
    ps, pe = _parse(prev.get("start")), _parse(prev.get("end"))
    if not all([cs, ce, ps, pe]):
        return False
    return (
        cs.month == 1
        and cs.day == 1
        and cs.year == ce.year
        and ps.month == 1
        and ps.day == 1
        and ps.year == cs.year - 1
        and pe.month == ce.month
        and pe.day == ce.day
    )


def revenue_drivers_comparison_label(result: dict) -> str:
    days = int(result.get("comparison_days") or 30)
    prior = result.get("prior_period") or {}
    if prior.get("start") and prior.get("end"):
        return (
            f"jämfört med föregående {days} dagarna "
            f"({format_date_range_sv(prior['start'], prior['end'])})"
        )
    return f"jämfört med föregående {days} dagarna"


def weekly_sales_comparison_label() -> str:
    return "jämfört med föregående avslutade vecka"


def build_comparison_context_block(
    raw_tool_results: list[tuple[str, dict]],
    question: str = "",
) -> str:
    """Injected into synthesis so the LLM must use explicit comparison wording."""
    lines: list[str] = []
    by_tool = {name: res for name, res in raw_tool_results if isinstance(res, dict)}

    for tool_name, result in by_tool.items():
        opening = result.get("period_label_opening")
        answer_phrase = result.get("period_label_answer")
        if answer_phrase:
            lines.append(
                f"PERIOD I SVARET: väv in '{answer_phrase}' naturligt efter slutsatsen "
                f"(helst i första eller andra meningen). "
                "Börja INTE med 'Under perioden', rå ISO-datum eller leverantörsnamn. "
                f"Använd inte '{opening}' som inledning."
            )
            break

    if "get_supplier_kpis" in by_tool:
        kpi = by_tool["get_supplier_kpis"]
        dr = kpi.get("date_range") or {}
        lines.append(f"Analyserad period (KPI): {analyzed_period_label(dr)}.")
        lines.append(
            f"OBLIGATORISK JÄMFÖRELSETEXT för KPI: {kpi_comparison_label(kpi)}. "
            "Använd exakt denna formulering när du jämför omsättning, ordrar eller enheter."
        )

    if "get_market_share" in by_tool:
        ms = by_tool["get_market_share"]
        category = ms.get("category_name") or "kategorin"
        period_phrase = ms.get("period_label_answer") or chart_period_suffix(
            ms.get("_period_kind") or infer_period_kind(ms.get("date_range") or {}, message=question),
            ms.get("date_range"),
            question,
        )
        lines.append(
            f"Marknadsandel inom {category} · {period_phrase}. "
            "Börja direkt med er andel i procent — väv in kategori och period naturligt i första meningen."
        )

    if "get_revenue_drivers" in by_tool:
        lines.append(
            f"Jämförelsebas (drivare): {revenue_drivers_comparison_label(by_tool['get_revenue_drivers'])}."
        )

    if "get_sales_over_time" in by_tool:
        sales = by_tool["get_sales_over_time"]
        dr = sales.get("date_range") or {}
        if sales.get("completed_week_label") or sales.get("granularity") == "week":
            comp = sales.get("comparison_note") or weekly_sales_comparison_label()
            lines.append(f"Veckojämförelse: {comp}")
        elif dr:
            lines.append(f"Trendperiod: {analyzed_period_label(dr)}.")

    if "get_declining_products" in by_tool:
        dec = by_tool["get_declining_products"]
        products = dec.get("products") or []
        if not products:
            lines.append(
                "INGA PRODUKTER I NEDGÅNG: products-listan är tom. "
                "Säg att inga produkter har negativ omsättningsförändring i vald jämförelse. "
                "Nämn INGEN produkt som tappat."
            )
        else:
            comp_label = dec.get("comparison_period_label") or decline_comparison_period_label(dec)
            lines.append(
                f"Produktnedgång — {comp_label}. "
                "Nämn ENDAST produkter som finns i products-listan."
            )
            prior = dec.get("prior_period") or {}
            if prior.get("start") and prior.get("end"):
                lines.append(
                    f"Jämförelsebas: {comp_label}"
                )

    if "get_top_products" in by_tool:
        top = by_tool["get_top_products"]
        products = top.get("products") or []
        limit = top.get("requested_limit") or len(products)
        lines.append(
            f"TOPPRODUKTGRÄNS: returnera exakt {limit} produkter — nämn aldrig #{(limit + 1)} eller fler."
        )

    if not lines:
        return ""
    return "\n\nJÄMFÖRELSE- OCH PERIODKRAV:\n" + "\n".join(f"- {ln}" for ln in lines)


def comparison_metadata(raw_tool_results: list[tuple[str, dict]]) -> dict:
    """Structured comparison fields for tests and optional metadata."""
    meta: dict = {}
    by_tool = {name: res for name, res in raw_tool_results if isinstance(res, dict)}
    if "get_supplier_kpis" in by_tool:
        meta["kpi_comparison_label"] = kpi_comparison_label(by_tool["get_supplier_kpis"])
    if "get_market_share" in by_tool:
        ms = by_tool["get_market_share"]
        meta["market_share_period_label"] = market_share_period_label(ms)
        meta["analyzed_date_range"] = ms.get("date_range")
    return meta
