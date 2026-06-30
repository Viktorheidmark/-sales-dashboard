"""
Deterministic Swedish labels for analyzed periods and comparison baselines.

Derived only from verified MCP tool payloads — never from LLM text.
"""

from __future__ import annotations

import re
from datetime import date
from typing import TYPE_CHECKING, Optional

from app.services.period_labels import message_specifies_period
from app.services.period_utils import format_date_range_sv, is_current_year_phrase

if TYPE_CHECKING:
    from app.services.intent_router import PriorTurnContext
from app.services.period_labels import (
    answer_period_phrase,
    chart_period_suffix,
    decline_comparison_period_label,
    infer_period_kind,
)

_COMPARISON_REQUEST_RE = re.compile(
    r"(\bjämför(?:a|er|t)?\b|jämfört|bättre\s+än|sämre\s+än|skillnad|periodjämförelse|"
    r"mot\s+föregående|mot\s+tidigare|föregående\s+period|tidigare\s+period|"
    r"förra\s+(året|månaden|veckan|perioden)|samma\s+period\s+förra)",
    re.IGNORECASE,
)

_COMPARE_INTENT_VAGUE_RE = re.compile(
    r"(\bjämför(?:a|er|t)?\b|\bjämförelse\b|jämfört|bättre|sämre|skillnad|periodjämförelse|mot\s+föregående|mot\s+tidigare)",
    re.IGNORECASE,
)

_AMBIGUOUS_COMPARE_RE = re.compile(
    r"(\bjämför(?:a|er|t)?\b|\bjämförelse\b|jämfört|skillnad|skiljer|periodjämförelse|"
    r"mot\s+(?:föregående|tidigare|förut)|föregående\s+period|förra\s+perioden|"
    r"ökat\s+eller\s+minskat|minskat\s+eller\s+ökat|"
    r"från\s+förut|skillnaden\s+mellan|hur\s+skiljer)",
    re.IGNORECASE,
)

_PRODUCT_EXTREMES_COMPARE_RE = re.compile(
    r"("
    r"(?:bäst|bästa|starkast|högst).{0,80}(?:sämst|sämsta|svagast|lägst)|"
    r"(?:sämst|sämsta|svagast|lägst).{0,80}(?:bäst|bästa|starkast|högst)|"
    r"den\s+(?:produkt\w*\s+)?som\s+går\s+bäst.{0,60}den\s+(?:produkt\w*\s+)?som\s+går\s+sämst"
    r")",
    re.IGNORECASE | re.DOTALL,
)

_TIME_PERIOD_COMPARE_CUE_RE = re.compile(
    r"("
    r"två\s+tidsperioder|"
    r"jämför\w*.{0,40}(?:senaste|föregående|förra)\s+\d+\s+dag|"
    r"jämför\w*.{0,40}(?:mars|februari|april|maj|juni|juli|augusti|september|oktober|november|december)|"
    r"(?:mars|februari|april|maj|juni|juli|augusti|september|oktober|november|december).{0,30}jämför\w*|"
    r"jämför\w*.{0,30}(?:i\s+år|detta\s+år|förra\s+året)|"
    r"försäljning.{0,40}(?:förra\s+perioden|föregående\s+period|tidigare\s+period)|"
    r"(?:förra\s+perioden|föregående\s+period|tidigare\s+period).{0,40}försäljning|"
    r"mot\s+(?:föregående|tidigare|förut)|"
    r"med\s+(?:föregående|tidigare|förut)|"
    r"ökat\s+eller\s+minskat|minskat\s+eller\s+ökat|"
    r"hur\s+skiljer|skillnaden\s+mellan\s+period"
    r")",
    re.IGNORECASE | re.DOTALL,
)

_REGION_COMPARE_RE = re.compile(
    r"("
    r"jämför\w*.{0,40}region|"
    r"region\w*.{0,40}jämför\w*|"
    r"jämför\w*.{0,40}(?:stockholm|göteborg|malmö)"
    r")",
    re.IGNORECASE | re.DOTALL,
)

_EXPLICIT_ROLLING_PAIR_RE = re.compile(
    r"senaste\s+(\d+)\s+dag(?:arna)?(?:\s+då)?"
    r".{0,40}(?:mot|jämfört\s+med)\s+(?:föregående|förra)\s+\1\s+dag",
    re.IGNORECASE | re.DOTALL,
)

_YTD_YOY_PAIR_RE = re.compile(
    r"(?:i\s+år|detta\s+år|hittills\s+i\s+år).{0,40}(?:jämfört\s+med|mot)\s+förra\s+året|"
    r"(?:jämfört\s+med|mot)\s+förra\s+året.{0,40}(?:i\s+år|detta\s+år|hittills\s+i\s+år)|"
    r"jämför\s+(?:i\s+år|detta\s+år).{0,30}förra\s+året",
    re.IGNORECASE | re.DOTALL,
)

_MARKET_SHARE_COMPARE_RE = re.compile(
    r"(marknadsandel|konkurrent|konkurrenter|märke|varumärke)",
    re.IGNORECASE,
)

_WEEKLY_FACTUAL_QUESTION_RE = re.compile(
    r"(hur såg försäljningen ut|hur gick veckan|senaste\s+veck)",
    re.IGNORECASE,
)

_ROLLING_CHANGE_RE = re.compile(
    r"(drev|drivare|förändring|förändrats|tappat|minskat|nedgång|fallit|sjunk)",
    re.IGNORECASE,
)

_COMPARISON_ONLY_PRIOR_TOOLS = frozenset({"get_revenue_drivers", "get_declining_products"})
_COMPARISON_ONLY_PRIOR_INTENTS = frozenset({"revenue_drivers", "product_decline"})
_REUSABLE_PRIOR_INTENTS = frozenset({
    "sales_trend",
    "sales_overview",
    "product_ranking",
    "region_ranking",
    "market_share",
    "unknown",
})

# Minimum share of current revenue for a prior-period KPI baseline to be cited in prose.
_MEANINGFUL_PRIOR_REVENUE_RATIO = 0.05

COMPARISON_PERIOD_CLARIFICATION = (
    'Vilka två tidsperioder vill du jämföra? Du kan exempelvis skriva '
    '"senaste 30 dagarna mot föregående 30 dagar", "i år jämfört med förra året" '
    'eller "april mot maj".'
)

COMPARISON_TWO_PERIODS_CLARIFICATION = "Vilka två tidsperioder vill du jämföra?"

COMPARISON_DIMENSION_CLARIFICATION = (
    "Vad vill du jämföra – produkter, regioner eller två tidsperioder?"
)

ComparisonDimension = str  # product | region | period | ambiguous | none


def message_specifies_analyzed_period(message: str) -> bool:
    """True when the user named the analyzed window (not only the comparison baseline)."""
    return message_specifies_period(message)


def question_requests_comparison(question: str) -> bool:
    """True when the user explicitly asked for a period comparison."""
    return bool(_COMPARISON_REQUEST_RE.search((question or "").strip()))


def is_product_extremes_comparison(message: str) -> bool:
    """Best-vs-worst product comparison (not period or generic ranking)."""
    msg = (message or "").strip()
    if not msg or not _PRODUCT_EXTREMES_COMPARE_RE.search(msg):
        return False
    if re.search(r"produkt", msg, re.IGNORECASE):
        return True
    return bool(re.search(r"den\s+(?:produkt\w*\s+)?som\s+går", msg, re.IGNORECASE))


def is_region_comparison_request(message: str) -> bool:
    """Explicit region-to-region comparison intent."""
    msg = (message or "").strip()
    if not msg:
        return False
    return bool(_REGION_COMPARE_RE.search(msg))


def wants_time_period_comparison(message: str) -> bool:
    """User is asking to compare time periods (explicit or implied)."""
    msg = (message or "").strip()
    if not msg:
        return False
    if message_has_explicit_comparison_pair(msg):
        return True
    return bool(_TIME_PERIOD_COMPARE_CUE_RE.search(msg))


def has_generic_comparison_intent(message: str) -> bool:
    """Broad comparison cue without a resolved dimension."""
    msg = (message or "").strip()
    if not msg:
        return False
    return bool(
        _AMBIGUOUS_COMPARE_RE.search(msg)
        or _COMPARE_INTENT_VAGUE_RE.search(msg)
        or question_requests_comparison(msg)
    )


def classify_comparison_dimension(message: str) -> ComparisonDimension:
    """Resolve what the user wants to compare before assuming dates."""
    msg = (message or "").strip()
    if not msg:
        return "none"

    from app.analytics.planner import parse_explicit_comparison

    if parse_explicit_comparison(msg) is not None:
        return "period"

    if not has_generic_comparison_intent(msg):
        return "none"
    if is_product_extremes_comparison(msg):
        return "product"
    if is_region_comparison_request(msg):
        return "region"
    if wants_time_period_comparison(msg):
        return "period"
    return "ambiguous"


def comparison_needs_dimension_clarification(
    message: str,
    prior: Optional["PriorTurnContext"] = None,
) -> bool:
    """Vague comparison without a clear product/region/period dimension."""
    from app.services.decline_period import prior_awaiting_decline_period

    if prior_awaiting_decline_period(prior):
        return False
    return classify_comparison_dimension(message) == "ambiguous"


def has_ambiguous_comparison_intent(message: str) -> bool:
    """True when the message implies comparison but does not name both windows."""
    msg = (message or "").strip()
    return bool(
        _AMBIGUOUS_COMPARE_RE.search(msg)
        or _COMPARE_INTENT_VAGUE_RE.search(msg)
        or question_requests_comparison(msg)
    )


def message_has_explicit_comparison_pair(message: str) -> bool:
    """True when both comparison windows are clearly stated or reliably inferable."""
    msg = (message or "").strip()
    if not msg:
        return False
    if _EXPLICIT_ROLLING_PAIR_RE.search(msg):
        return True
    if _YTD_YOY_PAIR_RE.search(msg):
        return True
    if (
        re.search(r"senaste\s+\d+\s+dag", msg, re.IGNORECASE)
        and re.search(
            r"(?:föregående|förra)\s+\d+\s+dag|föregående\s+\d+\s+dagarna",
            msg,
            re.IGNORECASE,
        )
    ):
        return True
    if is_current_year_phrase(msg) and re.search(r"förra\s+året", msg, re.IGNORECASE):
        if re.search(r"jämför|jämfört|mot", msg, re.IGNORECASE):
            return True
    return False


def is_rolling_change_question(message: str) -> bool:
    """Rolling N-day change analysis — not an open-ended period comparison."""
    from app.services.decline_period import is_decline_ranking_question

    msg = (message or "").strip()
    if not message_specifies_analyzed_period(msg):
        return False
    if is_decline_ranking_question(msg):
        return True
    if _ROLLING_CHANGE_RE.search(msg) and re.search(r"försäljning|omsättning|intäkt", msg, re.I):
        return True
    return False


def prior_has_reusable_period(prior: Optional["PriorTurnContext"]) -> bool:
    """True when the immediately preceding turn was a single-period analysis."""
    if not prior or not prior.tool_calls:
        return False
    if any(t in _COMPARISON_ONLY_PRIOR_TOOLS for t in prior.tool_calls):
        return False

    from app.services.follow_up_context import analysis_context_from_prior_data

    ctx = analysis_context_from_prior_data(
        prior.question,
        list(prior.tool_calls),
        list(prior.sources),
        prior.analysis_context,
    )
    if not ctx or not ctx.start_date or not ctx.end_date:
        return False
    if ctx.prior_intent in _COMPARISON_ONLY_PRIOR_INTENTS:
        return False
    if ctx.prior_intent not in _REUSABLE_PRIOR_INTENTS:
        return False
    return True


def comparison_needs_period_clarification(
    message: str,
    prior: Optional["PriorTurnContext"] = None,
) -> bool:
    """Time-period comparison without enough period detail — ask before fetching data."""
    from app.services.decline_period import (
        is_decline_ranking_question,
        prior_awaiting_decline_period,
    )

    if prior_awaiting_decline_period(prior):
        return False

    msg = (message or "").strip()
    if not msg or _MARKET_SHARE_COMPARE_RE.search(msg):
        return False
    if is_decline_ranking_question(msg):
        return False
    if is_rolling_change_question(msg):
        return False

    dimension = classify_comparison_dimension(msg)
    if dimension in ("none", "product", "region", "ambiguous"):
        return False
    if dimension == "period":
        if message_has_explicit_comparison_pair(msg):
            return False
        if prior_has_reusable_period(prior):
            return False
        return True

    if not has_ambiguous_comparison_intent(msg):
        return False
    if message_has_explicit_comparison_pair(msg):
        return False
    if prior_has_reusable_period(prior):
        return False
    return True


def kpi_comparison_is_meaningful(result: dict) -> bool:
    """False when prior-period KPI data is missing or too thin to compare fairly."""
    prior_raw = result.get("prev_total_revenue")
    if prior_raw is None:
        return False
    prior_rev = float(prior_raw)
    curr_rev = float(result.get("total_revenue") or 0)
    if prior_rev <= 0 or curr_rev <= 0:
        return False
    if int(result.get("prev_total_orders") or 0) <= 0:
        return False
    if prior_rev / curr_rev < _MEANINGFUL_PRIOR_REVENUE_RATIO:
        return False
    return True


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


def rolling_change_comparison_label(result: dict) -> str:
    """Both resolved windows for rolling N-day change analysis."""
    days = int(result.get("comparison_days") or 30)
    current = result.get("current_period") or result.get("latest_period") or {}
    prior = result.get("prior_period") or {}
    cs, ce = current.get("start"), current.get("end")
    ps, pe = prior.get("start"), prior.get("end")

    current_phrase = f"Senaste {days} dagarna"
    if cs and ce:
        current_phrase = f"{current_phrase} ({format_date_range_sv(cs, ce)})"

    prior_phrase = f"föregående {days} dagar"
    if ps and pe:
        prior_phrase = f"{prior_phrase} ({format_date_range_sv(ps, pe)})"

    return f"{current_phrase} jämfört med {prior_phrase}"


def kpi_comparison_label(result: dict) -> str:
    """Label for get_supplier_kpis comparison baseline — both windows explicit."""
    prev = result.get("prev_date_range") or {}
    curr = result.get("date_range") or {}
    if not prev.get("start") or not prev.get("end"):
        days = _period_days(curr.get("start", ""), curr.get("end", ""))
        return f"Senaste {days} dagarna jämfört med föregående {days} dagar" if days else ""

    prev_start, prev_end = prev["start"], prev["end"]
    curr_start, curr_end = curr.get("start"), curr.get("end")
    kind = result.get("comparison_kind")

    if kind == "explicit_period_comparison" and result.get("comparison_mode", "custom") == "custom":
        # Custom date range — always use exact dates, no rolling terminology
        curr_label = format_date_range_sv(curr_start, curr_end) if curr_start and curr_end else "analyserad period"
        prev_label = format_date_range_sv(prev_start, prev_end)
        return f"{curr_label} jämfört med {prev_label}"

    if kind == "year_over_year" or _is_yoy_kpi_comparison(result):
        curr_part = (
            f"Hittills i år ({format_date_range_sv(curr_start, curr_end)})"
            if curr_start and curr_end
            else "Hittills i år"
        )
        return (
            f"{curr_part} jämfört med samma period föregående år "
            f"({format_date_range_sv(prev_start, prev_end)})"
        )

    days = _period_days(curr.get("start", ""), curr.get("end", ""))
    curr_part = f"Senaste {days} dagarna"
    if curr_start and curr_end:
        curr_part = f"{curr_part} ({format_date_range_sv(curr_start, curr_end)})"
    prior_part = f"föregående {days} dagar ({format_date_range_sv(prev_start, prev_end)})"
    return f"{curr_part} jämfört med {prior_part}"


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
    return rolling_change_comparison_label(result)


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
        lines.append(
            f"Analyserad period (KPI): {analyzed_period_label(dr, message=question)}."
        )
        wants_compare = (
            message_has_explicit_comparison_pair(question)
            or question_requests_comparison(question)
        )
        if wants_compare and kpi_comparison_is_meaningful(kpi):
            lines.append(
                f"OBLIGATORISK JÄMFÖRELSETEXT för KPI: {kpi_comparison_label(kpi)}. "
                "Använd exakt denna formulering när du jämför omsättning, ordrar eller enheter. "
                "Nämn ALDRIG en ospecificerad 'förra perioden'."
            )
        elif wants_compare:
            lines.append(
                "Jämförelse efterfrågad men ingen tillförlitlig jämförelsebas i datan för vald period. "
                "Säg det tydligt — hitta inte på procent, datumintervall eller tidigare omsättning."
            )
        else:
            lines.append(
                "Nämn INTE procentuell förändring, 'jämfört med föregående period' eller tidigare omsättning "
                "om användaren inte uttryckligen bad om jämförelse."
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
        label = revenue_drivers_comparison_label(by_tool["get_revenue_drivers"])
        lines.append(
            f"OBLIGATORISK JÄMFÖRELSETEXT (drivare): {label}. "
            "Använd exakt denna formulering. Nämn ALDRIG en ospecificerad 'förra perioden'."
        )

    if "get_sales_over_time" in by_tool:
        sales = by_tool["get_sales_over_time"]
        dr = sales.get("date_range") or {}
        if sales.get("completed_week_label") or (
            _WEEKLY_FACTUAL_QUESTION_RE.search(question)
            and sales.get("granularity") == "week"
        ):
            comp = sales.get("comparison_note") or weekly_sales_comparison_label()
            lines.append(f"Veckojämförelse: {comp}")
        elif dr:
            lines.append(f"Trendperiod: {analyzed_period_label(dr, message=question)}.")

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
                "Nämn ENDAST produkter som finns i products-listan. "
                "Nämn ALDRIG en ospecificerad 'förra perioden'."
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


def comparison_metadata(
    raw_tool_results: list[tuple[str, dict]],
    question: str = "",
) -> dict:
    """Structured comparison fields for tests and optional metadata."""
    meta: dict = {}
    by_tool = {name: res for name, res in raw_tool_results if isinstance(res, dict)}
    if "get_supplier_kpis" in by_tool:
        kpi = by_tool["get_supplier_kpis"]
        wants_compare = (
            message_has_explicit_comparison_pair(question)
            or question_requests_comparison(question)
        )
        if wants_compare and kpi_comparison_is_meaningful(kpi):
            meta["kpi_comparison_label"] = kpi_comparison_label(kpi)
    if "get_market_share" in by_tool:
        ms = by_tool["get_market_share"]
        meta["market_share_period_label"] = market_share_period_label(ms)
        meta["analyzed_date_range"] = ms.get("date_range")
    return meta
