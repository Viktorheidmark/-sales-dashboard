"""
Deterministic Swedish labels for analyzed periods and comparison baselines.

Derived only from verified MCP tool payloads — never from LLM text.
"""

from __future__ import annotations

from datetime import date

from app.services.period_utils import format_date_range_sv


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


def analyzed_period_label(date_range: dict | None, *, prefix: str = "") -> str:
    """Human-readable label for the primary analyzed window."""
    if not date_range or not date_range.get("start") or not date_range.get("end"):
        return prefix or "vald period"
    start, end = date_range["start"], date_range["end"]
    span = _period_days(start, end)
    s_d, e_d = _parse(start), _parse(end)
    if s_d and e_d and s_d.month == 1 and s_d.day == 1 and s_d.year == e_d.year:
        return f"hittills i år ({format_date_range_sv(start, end)})"
    if span == 90:
        return f"de senaste 90 dagarna ({format_date_range_sv(start, end)})"
    if span == 30:
        return f"de senaste 30 dagarna ({format_date_range_sv(start, end)})"
    body = format_date_range_sv(start, end)
    return f"{prefix}{body}".strip() if prefix else body


def market_share_period_label(result: dict) -> str:
    category = result.get("category_name") or "kategorin"
    dr = result.get("date_range") or {}
    period = analyzed_period_label(dr)
    if dr and _period_days(dr.get("start", ""), dr.get("end", "")) == 90:
        return f"Marknadsandel inom {category} de senaste 90 dagarna"
    return f"Marknadsandel inom {category}, {period}"


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


def build_comparison_context_block(raw_tool_results: list[tuple[str, dict]]) -> str:
    """Injected into synthesis so the LLM must use explicit comparison wording."""
    lines: list[str] = []
    by_tool = {name: res for name, res in raw_tool_results if isinstance(res, dict)}

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
        lines.append(
            f"OBLIGATORISK PERIOD I SVARET: {market_share_period_label(ms)}. "
            "Nämn alltid kategori och tidsperiod i första meningen."
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
        days = int(dec.get("comparison_days") or 30)
        prior = dec.get("prior_period") or {}
        if prior.get("start") and prior.get("end"):
            lines.append(
                f"Produktnedgång jämfört med föregående {days} dagarna "
                f"({format_date_range_sv(prior['start'], prior['end'])})."
            )
        else:
            lines.append(f"Produktnedgång jämfört med föregående {days} dagarna.")

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
