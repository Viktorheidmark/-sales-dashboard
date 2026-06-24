"""
Deterministic intent routing for analytics chat.

Resolves which MCP tool(s) must run for common Swedish question patterns
when the LLM might otherwise skip tool calls (e.g. missing category_name).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Optional

from app.services.period_utils import (
    align_weekly_query_bounds,
    completed_week_bounds,
    is_current_year_phrase,
    resolve_period_range,
)
from app.services.ranking_limits import resolve_product_ranking_limit
from app.services.period_labels import infer_period_kind

CATEGORIES = ("Läsk", "Chips & snacks")
KNOWN_REGIONS = ("Stockholm", "Göteborg", "Malmö", "Uppsala", "Västerås", "Örebro", "Linköping", "Helsingborg")

CHART_TOOL_PRIORITY = [
    "get_revenue_drivers",
    "get_market_share",
    "get_top_products",
    "get_declining_products",
    "get_sales_by_region",
    "get_sales_over_time",
]

_MARKET_SHARE_RE = re.compile(
    r"(marknadsandel|market\s+share|"
    r"konkurrent|konkurrenter|"
    r"vårt märke|vårt varumärke|vår andel|"
    r"jämfört med konkurrenter|jämfört med konkurrenterna|"
    r"mot konkurrenter|mot konkurrenterna|"
    r"hur går det för vårt märke)",
    re.IGNORECASE,
)

_TOP_PRODUCTS_RE = re.compile(
    r"("
    r"(produkt|produkter).{0,50}(bäst|säljer|topp|störst|mest)|"
    r"(bäst|topp|störst|mest).{0,50}(produkt|produkter)"
    r")",
    re.IGNORECASE | re.DOTALL,
)

_ALL_PRODUCTS_COMPARE_RE = re.compile(
    r"("
    r"(jämför|jämföra|visa|ranka).{0,80}(alla|samtliga)\s+produkter|"
    r"(alla|samtliga)\s+produkter.{0,80}(jämför|försäljning|omsättning|rank)"
    r")",
    re.IGNORECASE | re.DOTALL,
)

_SALES_TREND_RE = re.compile(
    r"("
    r"(försäljning|utvecklat|utveckling|trend).{0,60}(90 dag|senaste 90|senaste veck|senaste \d+ dag)|"
    r"senaste (90 dag|\d+ dag|veck).{0,40}(försäljning|utvecklat|utveckling)|"
    r"hur såg försäljningen ut"
    r")",
    re.IGNORECASE | re.DOTALL,
)

_DECLINING_RE = re.compile(
    r"(nedgång|minskat|fallit|sjunk|tappat|produkt.{0,30}(minsk|nedgång|tapp))",
    re.IGNORECASE | re.DOTALL,
)

_SALES_BY_REGION_RE = re.compile(
    r"("
    r"vilken\s+region|"
    r"region.{0,50}(mest|störst|högst|intäkt|försäljning|omsättning)|"
    r"(mest|störst|högst).{0,50}(region|intäkt)"
    r")",
    re.IGNORECASE | re.DOTALL,
)

_FOCUS_RE = re.compile(
    r"(vad borde|vad bör|vad ska vi fokusera|fokusera på|prioritera|nästa period)",
    re.IGNORECASE,
)

_DIAGRAM_FOLLOWUP_RE = re.compile(
    r"("
    r"^\s*(?:kan du\s+)?(?:visa|visar|show)\s+(?:ett\s+)?(?:diagram|graf)(?:\s+för\s+det)?\s*\??\s*$|"
    r"^\s*visa\s+(?:diagram|graf)\s*\??\s*$|"
    r"^\s*kan du\s+visa\s+det\s+i\s+graf\??\s*$|"
    r"(?:visa|visar|show).{0,25}(?:diagram|graf)|"
    r"(?:diagram|graf).{0,15}för\s+det|"
    r"ett\s+diagram"
    r")",
    re.IGNORECASE | re.DOTALL,
)

_DAILY_TREND_EXPLICIT_RE = re.compile(
    r"(dag för dag|daglig\s+utveckling|per dag)",
    re.IGNORECASE,
)

_WEEKLY_SALES_RE = re.compile(r"senaste\s+veck|hur såg försäljningen ut", re.IGNORECASE)

_WEEKLY_CHART_LOOKBACK_WEEKS = 8

_LONG_TERM_TREND_RE = re.compile(
    r"("
    r"visa\s+(trenden|trend(?:\s+över\s+tid)?)|"
    r"(visa|se|hur\s+har).{0,40}(utveckling|trend).{0,30}(tid|veckor|månader)|"
    r"jämför.{0,30}(tidigare|veckor|perioder)|"
    r"senaste\s+(två|tre|fyra|2|3|4)\s+månader|"
    r"(8|åtta)\s+veckor|"
    r"över\s+tid"
    r")",
    re.IGNORECASE | re.DOTALL,
)

_KPI_COMPARISON_RE = re.compile(
    r"(föregående period|jämfört med förra|mot föregående|periodjämförelse|periodöversikt|"
    r"jämför.{0,30}(senaste|föregående|förra)|bättre än föregående)",
    re.IGNORECASE,
)

_TIME_SERIES_INTENT_RE = re.compile(
    r"(utvecklat|utveckling|trend|över\s+tid|vecka\s+för\s+vecka|dag\s+för\s+dag|försäljningstrend)",
    re.IGNORECASE,
)

_PERIOD_ONLY_FOLLOWUP_RE = re.compile(
    r"^("
    r"senaste\s+\d+\s+dag(?:arna)?(?:\s+då)?|"
    r"senaste\s+(?:veckan?|månaden?)(?:\s+då)?|"
    r"och\s+senaste\s+.+|"
    r"\d+\s+dag(?:arna)?\s+då"
    r")\s*\??$",
    re.IGNORECASE,
)

_SUBJECT_CHANGE_RE = re.compile(
    r"(marknadsandel|produkt|produkter|konkurrent|fokusera|region|kategori|mejeri|dryck)",
    re.IGNORECASE,
)

_PERIOD_RETAINED_TOOLS = frozenset({
    "get_sales_over_time",
    "get_sales_by_region",
    "get_top_products",
    "get_declining_products",
    "get_market_share",
    "get_revenue_drivers",
})

_REVENUE_30D_DEEP_DIVE_RE = re.compile(
    r"("
    r"hur\s+har\s+.{0,30}(försäljning|utvecklat|utveckling).{0,40}senaste\s+30\s+dag|"
    r"(försäljningen|försäljning).{0,20}(utvecklat|utveckling).{0,40}senaste\s+30\s+dag"
    r")",
    re.IGNORECASE | re.DOTALL,
)

_PRODUCT_DECLINE_30D_RE = re.compile(
    r"(produkt|produkter).{0,40}(tappat|minskat|nedgång|fallit|sjunk).{0,40}senaste\s+30\s+dag|"
    r"senaste\s+30\s+dag.{0,40}(produkt|produkter).{0,40}(tappat|minskat|nedgång)",
    re.IGNORECASE | re.DOTALL,
)

_DRIVER_GAINERS_FOLLOWUP_RE = re.compile(
    r"produkter\s+som\s+drev\s+ökningen|drev\s+ökningen",
    re.IGNORECASE,
)
_DRIVER_LOSERS_FOLLOWUP_RE = re.compile(
    r"produkter\s+som\s+tappade|som\s+tappade",
    re.IGNORECASE,
)
_DRIVER_REGIONS_FOLLOWUP_RE = re.compile(
    r"utveckling\s+per\s+region|per\s+region",
    re.IGNORECASE,
)
_PRODUCT_REGION_DECLINE_FOLLOWUP_RE = re.compile(
    r"tappet\s+per\s+region",
    re.IGNORECASE,
)
_PRODUCT_TREND_FOLLOWUP_RE = re.compile(
    r"produktens\s+utveckling|utveckling\s+över\s+tid",
    re.IGNORECASE,
)
_PRODUCT_COMPARE_FOLLOWUP_RE = re.compile(
    r"jämför\s+.+\s+med\s+övriga\s+produkter|övriga\s+produkter",
    re.IGNORECASE,
)

_YTD_DEVELOPMENT_RE = re.compile(
    r"hur\s+har\s+försäljningen\s+utvecklats",
    re.IGNORECASE,
)

_YTD_OVERVIEW_RE = re.compile(
    r"(hur\s+ser\s+försäljningen|överlag|hur\s+går\s+det)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ToolPlan:
    tool_name: str
    args: dict
    reason: str


@dataclass(frozen=True)
class PriorTurnContext:
    question: str
    answer: str = ""
    tool_calls: tuple[str, ...] = ()
    sources: tuple[dict[str, Any], ...] = ()
    has_chart: bool = False


def default_category_for_supplier(supplier_name: str) -> str:
    name = supplier_name.lower()
    if "coca-cola" in name or "cocacola" in name or "pepsi" in name:
        return "Läsk"
    if "orkla" in name or "snacks" in name or "estrella" in name or "olw" in name:
        return "Chips & snacks"
    return "Läsk"


def extract_category(message: str) -> Optional[str]:
    msg = message.lower()
    if "chips" in msg or "snacks" in msg:
        return "Chips & snacks"
    if "läsk" in msg or "dryck" in msg or "soda" in msg:
        return "Läsk"
    return None


def extract_region(message: str) -> Optional[str]:
    for region in KNOWN_REGIONS:
        if region.lower() in message.lower():
            return region
    return None


def is_diagram_followup_request(message: str) -> bool:
    return bool(_DIAGRAM_FOLLOWUP_RE.search(message.strip()))


def is_long_term_trend_request(message: str) -> bool:
    return bool(_LONG_TERM_TREND_RE.search(message.strip()))


def _extract_completed_week_from_prior(prior: "PriorTurnContext") -> tuple[date, date]:
    """Return (monday, sunday) of the completed week discussed in the prior answer.

    Reads the end date from prior sources.  Because weekly queries always end on
    a completed Sunday, the date_range.end IS the Sunday of the answer week.
    Falls back to the most-recently-completed week if sources are absent.
    """
    for source in prior.sources:
        dr = source.get("date_range") if isinstance(source, dict) else None
        if isinstance(dr, dict) and dr.get("end"):
            try:
                end_d = date.fromisoformat(str(dr["end"])[:10])
                # Sunday weekday == 6
                if end_d.weekday() == 6:
                    return end_d - timedelta(days=6), end_d
            except ValueError:
                pass
    return completed_week_bounds()


def is_period_only_followup(message: str) -> bool:
    msg = message.strip()
    if not msg or _SUBJECT_CHANGE_RE.search(msg):
        return False
    return bool(_PERIOD_ONLY_FOLLOWUP_RE.match(msg))


def extract_period_args(message: str, reference: Optional[date] = None) -> dict:
    """Derive start_date/end_date (and optional days) from relative Swedish period phrases."""
    return resolve_period_range(message, reference=reference)


def _period_kind_from_ui_args(args: dict) -> str:
    start, end = args.get("start_date"), args.get("end_date")
    if not start or not end:
        return "ui_default"
    try:
        span = (date.fromisoformat(str(end)[:10]) - date.fromisoformat(str(start)[:10])).days + 1
    except ValueError:
        return "ui_default"
    if span == 90:
        return "ui_default"
    if span == 30:
        return "ui_default_30"
    if span == 180:
        return "ui_default_180"
    return "exact_range"


def _period_args_from_message(
    message: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    prior: Optional[PriorTurnContext] = None,
    reference: Optional[date] = None,
) -> dict:
    """Message-resolved period overrides UI default date filters."""
    period_args = extract_period_args(message, reference=reference) if message else {}
    if period_args.get("start_date") and period_args.get("end_date"):
        out = {
            "start_date": period_args["start_date"],
            "end_date": period_args["end_date"],
        }
        if period_args.get("days") is not None:
            out["days"] = period_args["days"]
        if period_args.get("completed_week"):
            out["completed_week"] = True
        out["_period_kind"] = period_args.get("period_kind") or infer_period_kind(
            {"start": period_args["start_date"], "end": period_args["end_date"]},
            message=message,
        )
        out["_period_explicit"] = True
        return out
    out = _date_args(start_date, end_date, prior)
    out["_period_kind"] = _period_kind_from_ui_args(out)
    out["_period_explicit"] = False
    return out


def _ytd_monthly_trend_args(period_args: dict) -> dict:
    return {
        **period_args,
        "granularity": "month",
        "_chart_intent": "time_series",
        "_force_time_series": True,
    }


def _plan_ytd_tools(
    message: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[ToolPlan]:
    """Deterministic routing for current-calendar-year (YTD) questions."""
    if not is_current_year_phrase(message):
        return []

    period_args = _period_args_from_message(message, start_date, end_date)

    if (
        (_TOP_PRODUCTS_RE.search(message) or _ALL_PRODUCTS_COMPARE_RE.search(message))
        and not _DECLINING_RE.search(message)
    ):
        args = dict(period_args)
        region = extract_region(message)
        if region:
            args["region"] = region
        if _ALL_PRODUCTS_COMPARE_RE.search(message):
            args["limit"] = resolve_product_ranking_limit(message, all_products=True)
        else:
            args["limit"] = resolve_product_ranking_limit(message, is_ytd=True)
        return [ToolPlan(
            tool_name="get_top_products",
            args=args,
            reason="YTD product ranking",
        )]

    if _YTD_DEVELOPMENT_RE.search(message):
        return [ToolPlan(
            tool_name="get_sales_over_time",
            args=_ytd_monthly_trend_args(period_args),
            reason="YTD monthly development trend",
        )]

    if _YTD_OVERVIEW_RE.search(message):
        return [
            ToolPlan(
                tool_name="get_supplier_kpis",
                args=dict(period_args),
                reason="YTD KPI summary",
            ),
            ToolPlan(
                tool_name="get_sales_over_time",
                args=_ytd_monthly_trend_args(period_args),
                reason="YTD monthly overview chart",
            ),
        ]

    if re.search(r"försäljning", message, re.IGNORECASE):
        return [ToolPlan(
            tool_name="get_sales_over_time",
            args=_ytd_monthly_trend_args(period_args),
            reason="YTD monthly trend",
        )]

    return []


def _date_args(
    start_date: Optional[str],
    end_date: Optional[str],
    prior: Optional[PriorTurnContext] = None,
) -> dict:
    args: dict = {}
    if prior and prior.sources:
        for source in prior.sources:
            dr = source.get("date_range") if isinstance(source, dict) else None
            if isinstance(dr, dict) and dr.get("start") and dr.get("end"):
                args["start_date"] = dr["start"]
                args["end_date"] = dr["end"]
                return args
    if start_date:
        args["start_date"] = start_date
    if end_date:
        args["end_date"] = end_date
    return args


def _granularity_from_date_range(
    start_date: Optional[str],
    end_date: Optional[str],
    message: str = "",
) -> str:
    msg = message.lower()
    if _DAILY_TREND_EXPLICIT_RE.search(msg):
        return "day"
    if re.search(r"\bveck", msg) and not re.search(r"senaste\s+\d+\s+dag", msg):
        return "week"

    if start_date and end_date:
        try:
            start = date.fromisoformat(start_date[:10])
            end = date.fromisoformat(end_date[:10])
            span = (end - start).days + 1
            if span <= 14:
                return "day"
            if span <= 90:
                return "week"
            return "month"
        except ValueError:
            pass

    if re.search(r"\bdag", msg) and "90" not in msg:
        return "day"
    return "month"


def _align_sales_over_time_weekly(args: dict) -> dict:
    if args.get("granularity") != "week":
        return args
    start_s = args.get("start_date")
    end_s = args.get("end_date")
    if not start_s or not end_s:
        return args
    aligned = align_weekly_query_bounds(start_s, end_s)
    out = {**args, "start_date": aligned["start"], "end_date": aligned["end"]}
    if start_s != aligned["start"]:
        out["_requested_start_date"] = start_s
    return out


def _ensure_chartable_sales_window(args: dict, prior_question: str) -> dict:
    """Widen sales-over-time range so line charts have at least two buckets."""
    end_s = args.get("end_date")
    if not end_s:
        return args
    original_range = {
        "start": args.get("start_date"),
        "end": args.get("end_date"),
    }
    end_d = date.fromisoformat(end_s[:10])
    start_s = args.get("start_date")
    start_d = date.fromisoformat(start_s[:10]) if start_s else end_d
    span = (end_d - start_d).days + 1

    granularity = args.get("granularity") or _granularity_from_date_range(start_s, end_s, prior_question)

    if granularity == "week" and _needs_weekly_context_widen(args, prior_question, span):
        # Anchor to real today — not end_d (a completed Sunday misread as "today"
        # would shift chart_end one week too early).
        _, chart_end = completed_week_bounds()
        chart_start = chart_end - timedelta(days=7 * _WEEKLY_CHART_LOOKBACK_WEEKS - 1)
        chart_start = chart_start - timedelta(days=chart_start.weekday())
        widened = {
            **args,
            "start_date": chart_start.isoformat(),
            "end_date": chart_end.isoformat(),
            "granularity": "week",
            "_chart_context_widened": True,
            "_original_date_range": original_range,
            "_chart_lookback_weeks": _WEEKLY_CHART_LOOKBACK_WEEKS,
        }
        return _align_sales_over_time_weekly(widened)

    if granularity == "day" and span < 14:
        return {
            **args,
            "start_date": (end_d - timedelta(days=13)).isoformat(),
            "end_date": end_d.isoformat(),
            "granularity": "day",
        }

    if granularity == "month" and span < 60:
        return {
            **args,
            "start_date": (end_d - timedelta(days=89)).isoformat(),
            "end_date": end_d.isoformat(),
            "granularity": "month",
        }

    return args


def _needs_weekly_context_widen(args: dict, prior_question: str, span: int) -> bool:
    """Widen to 8 completed weeks only for single-week summary questions."""
    if args.get("completed_week"):
        return True
    if span <= 7:
        return True
    if _WEEKLY_SALES_RE.search(prior_question) and span <= 14:
        return True
    return False


def _primary_chart_tool(tool_calls: list[str]) -> Optional[str]:
    for tool in CHART_TOOL_PRIORITY:
        if tool in tool_calls:
            return tool
    if "get_supplier_kpis" in tool_calls:
        return "get_sales_over_time"
    return tool_calls[0] if tool_calls else None


def _reconstruct_tool_args(
    tool_name: str,
    prior: PriorTurnContext,
    supplier_name: str,
    start_date: Optional[str],
    end_date: Optional[str],
    message: str = "",
) -> dict:
    period_args = extract_period_args(message) if message else {}
    if period_args.get("start_date") and period_args.get("end_date"):
        args = {
            "start_date": period_args["start_date"],
            "end_date": period_args["end_date"],
        }
        if period_args.get("completed_week"):
            args["completed_week"] = True
    else:
        args = _date_args(start_date, end_date, prior)

    q = prior.question
    period_message = message or q

    if tool_name == "get_market_share":
        args["category_name"] = extract_category(q) or default_category_for_supplier(supplier_name)
    elif tool_name == "get_top_products":
        region = extract_region(q)
        if region:
            args["region"] = region
        args["limit"] = resolve_product_ranking_limit(
            period_message,
            is_ytd=is_current_year_phrase(period_message),
        )
    elif tool_name == "get_declining_products":
        args["days"] = period_args.get("days", 30)
        args["limit"] = 5
        if prior and "get_declining_products" in prior.tool_calls:
            q_lower = (message or q).lower()
            if _PRODUCT_REGION_DECLINE_FOLLOWUP_RE.search(q_lower):
                args["_deep_dive_focus"] = "regions"
            elif _PRODUCT_TREND_FOLLOWUP_RE.search(q_lower):
                args["_deep_dive_focus"] = "product_trend"
            elif _PRODUCT_COMPARE_FOLLOWUP_RE.search(q_lower):
                args["_deep_dive_focus"] = "portfolio"
    elif tool_name == "get_revenue_drivers":
        args["days"] = period_args.get("days", 30)
        args["limit"] = 5
        if prior and "get_revenue_drivers" in prior.tool_calls:
            q_lower = (message or q).lower()
            if _DRIVER_GAINERS_FOLLOWUP_RE.search(q_lower):
                args["_deep_dive_focus"] = "gainers"
            elif _DRIVER_LOSERS_FOLLOWUP_RE.search(q_lower):
                args["_deep_dive_focus"] = "losers"
            elif _DRIVER_REGIONS_FOLLOWUP_RE.search(q_lower):
                args["_deep_dive_focus"] = "regions"
    elif tool_name == "get_sales_over_time":
        args["granularity"] = _granularity_from_date_range(
            args.get("start_date"),
            args.get("end_date"),
            period_message,
        )
        args = _align_sales_over_time_weekly(args)
    return args


def plan_followup_tools(
    message: str,
    prior: PriorTurnContext,
    supplier_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[ToolPlan]:
    if not is_diagram_followup_request(message):
        return []
    if prior.has_chart:
        return []
    if not prior.tool_calls:
        return []

    primary = _primary_chart_tool(list(prior.tool_calls))
    if not primary:
        return []

    # "visa diagram" after a weekly-sales answer → daily chart for the EXACT answered week.
    # Do NOT widen to 8 weeks: the user asked to visualise the same period as the answer.
    if primary == "get_sales_over_time" and _WEEKLY_SALES_RE.search(prior.question or ""):
        week_start, week_end = _extract_completed_week_from_prior(prior)
        return [ToolPlan(
            tool_name="get_sales_over_time",
            args={
                "start_date": week_start.isoformat(),
                "end_date": week_end.isoformat(),
                "granularity": "day",
            },
            reason="daily chart for answered week",
        )]

    args = _reconstruct_tool_args(
        primary, prior, supplier_name, start_date, end_date, message=prior.question,
    )
    if primary == "get_sales_over_time":
        args = _ensure_chartable_sales_window(args, prior.question)
        args["granularity"] = _granularity_from_date_range(
            args.get("start_date"),
            args.get("end_date"),
            prior.question,
        )

    return [ToolPlan(
        tool_name=primary,
        args=args,
        reason=f"follow-up chart ({primary})",
    )]


def plan_long_term_trend_tools(
    message: str,
    prior: PriorTurnContext,
    supplier_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[ToolPlan]:
    """Return an 8-week context chart when the user explicitly asks for long-term trend.

    Only triggers when the prior question was a sales-over-time query and the
    current message contains explicit long-term language such as 'visa trenden',
    'visa utvecklingen över tid', 'jämför med tidigare veckor', etc.
    """
    if not is_long_term_trend_request(message):
        return []
    if not prior.tool_calls:
        return []

    primary = _primary_chart_tool(list(prior.tool_calls))
    if primary not in ("get_sales_over_time", "get_supplier_kpis"):
        return []

    args = _reconstruct_tool_args(
        "get_sales_over_time", prior, supplier_name, start_date, end_date,
        message=prior.question,
    )
    args = _ensure_chartable_sales_window(args, prior.question)
    args["granularity"] = "week"
    return [ToolPlan(
        tool_name="get_sales_over_time",
        args=args,
        reason="explicit long-term trend (8-week context)",
    )]


def plan_period_followup_tools(
    message: str,
    prior: PriorTurnContext,
    supplier_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[ToolPlan]:
    if not is_period_only_followup(message):
        return []
    if not prior.tool_calls:
        return []

    primary = _primary_chart_tool(list(prior.tool_calls))
    if not primary or primary not in _PERIOD_RETAINED_TOOLS:
        return []

    return [ToolPlan(
        tool_name=primary,
        args=_reconstruct_tool_args(primary, prior, supplier_name, start_date, end_date, message=message),
        reason=f"period follow-up ({primary})",
    )]


def plan_deep_dive_followup_tools(
    message: str,
    prior: PriorTurnContext,
    supplier_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[ToolPlan]:
    if not prior.tool_calls:
        return []

    msg = message.strip()
    period_args = extract_period_args(msg)
    days = period_args.get("days", 30)

    if "get_revenue_drivers" in prior.tool_calls:
        if _DRIVER_GAINERS_FOLLOWUP_RE.search(msg) or _DRIVER_LOSERS_FOLLOWUP_RE.search(msg) or _DRIVER_REGIONS_FOLLOWUP_RE.search(msg):
            args = {"days": days, "limit": 5}
            if _DRIVER_GAINERS_FOLLOWUP_RE.search(msg):
                args["_deep_dive_focus"] = "gainers"
            elif _DRIVER_LOSERS_FOLLOWUP_RE.search(msg):
                args["_deep_dive_focus"] = "losers"
            else:
                args["_deep_dive_focus"] = "regions"
            return [ToolPlan("get_revenue_drivers", args, reason="revenue drivers follow-up")]

    if "get_declining_products" in prior.tool_calls:
        if (
            _PRODUCT_REGION_DECLINE_FOLLOWUP_RE.search(msg)
            or _PRODUCT_TREND_FOLLOWUP_RE.search(msg)
            or _PRODUCT_COMPARE_FOLLOWUP_RE.search(msg)
        ):
            args = {"days": days, "limit": 5}
            if _PRODUCT_REGION_DECLINE_FOLLOWUP_RE.search(msg):
                args["_deep_dive_focus"] = "regions"
            elif _PRODUCT_TREND_FOLLOWUP_RE.search(msg):
                args["_deep_dive_focus"] = "product_trend"
            else:
                args["_deep_dive_focus"] = "portfolio"
            return [ToolPlan("get_declining_products", args, reason="product decline follow-up")]

    return []


def plan_forced_tools(
    message: str,
    supplier_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    prior_context: Optional[PriorTurnContext] = None,
) -> list[ToolPlan]:
    """
    Return deterministic MCP tool plan(s) for well-known question shapes.
    Empty list means the LLM tool loop should decide.
    """
    msg = message.strip()
    plans: list[ToolPlan] = []

    if prior_context:
        deep_followup = plan_deep_dive_followup_tools(
            msg, prior_context, supplier_name, start_date, end_date,
        )
        if deep_followup:
            return deep_followup
        period_followup = plan_period_followup_tools(
            msg, prior_context, supplier_name, start_date, end_date,
        )
        if period_followup:
            return period_followup
        long_term = plan_long_term_trend_tools(
            msg, prior_context, supplier_name, start_date, end_date,
        )
        if long_term:
            return long_term
        followup = plan_followup_tools(msg, prior_context, supplier_name, start_date, end_date)
        if followup:
            return followup

    if is_diagram_followup_request(msg):
        return []

    if _FOCUS_RE.search(msg):
        args = _date_args(start_date, end_date)
        args.update({"days": 30, "limit": 5})
        plans.append(ToolPlan(
            tool_name="get_declining_products",
            args=args,
            reason="focus advisory — declining products",
        ))
        return plans

    if _PRODUCT_DECLINE_30D_RE.search(msg):
        args = _date_args(start_date, end_date)
        args.update({"days": 30, "limit": 5})
        plans.append(ToolPlan(
            tool_name="get_declining_products",
            args=args,
            reason="product decline deep dive (30 days)",
        ))
        return plans

    if _REVENUE_30D_DEEP_DIVE_RE.search(msg):
        period_args = extract_period_args(msg) or {"days": 30}
        days = period_args.get("days", 30)
        today = date.today()
        trend_start = (today - timedelta(days=days)).isoformat()
        trend_end = today.isoformat()
        plans.append(ToolPlan(
            tool_name="get_revenue_drivers",
            args={"days": days, "limit": 5, "_chart_intent": "drivers_data"},
            reason="30-day revenue drivers deep dive",
        ))
        plans.append(ToolPlan(
            tool_name="get_sales_over_time",
            args={
                "start_date": trend_start,
                "end_date": trend_end,
                "granularity": "week",
                "_chart_intent": "time_series",
                "_force_time_series": True,
            },
            reason="weekly trend for 30-day development question",
        ))
        return plans

    if _KPI_COMPARISON_RE.search(msg) and not _TIME_SERIES_INTENT_RE.search(msg):
        period_args = extract_period_args(msg) or {"days": 30}
        days = period_args.get("days", 30)
        plans.append(ToolPlan(
            tool_name="get_revenue_drivers",
            args={"days": days, "limit": 5, "_chart_intent": "period_comparison"},
            reason="explicit period comparison",
        ))
        return plans

    if _ALL_PRODUCTS_COMPARE_RE.search(msg) and not _DECLINING_RE.search(msg):
        args = _period_args_from_message(msg, start_date, end_date)
        args["limit"] = resolve_product_ranking_limit(msg, all_products=True)
        plans.append(ToolPlan(
            tool_name="get_top_products",
            args=args,
            reason="all products ranked for requested period",
        ))
        return plans

    ytd_plans = _plan_ytd_tools(msg, start_date, end_date)
    if ytd_plans:
        return ytd_plans

    if _SALES_TREND_RE.search(msg):
        args = _period_args_from_message(msg, start_date, end_date)
        args["granularity"] = _granularity_from_date_range(
            args.get("start_date"),
            args.get("end_date"),
            msg,
        )
        if _WEEKLY_SALES_RE.search(msg) and args.get("completed_week"):
            week_start, week_end = completed_week_bounds()
            prev_start = week_start - timedelta(days=7)
            args["start_date"] = prev_start.isoformat()
            args["end_date"] = week_end.isoformat()
            args["_suppress_chart"] = True
            args["_chart_intent"] = "weekly_kpi"
        args = _align_sales_over_time_weekly(args)
        # _ensure_chartable_sales_window only runs in plan_followup_tools (diagram requests).
        plans.append(ToolPlan(
            tool_name="get_sales_over_time",
            args=args,
            reason="sales trend",
        ))
        return plans

    if _SALES_BY_REGION_RE.search(msg) and not _TOP_PRODUCTS_RE.search(msg):
        args = _period_args_from_message(msg, start_date, end_date)
        plans.append(ToolPlan(
            tool_name="get_sales_by_region",
            args=args,
            reason="regional sales comparison",
        ))
        return plans

    if _DECLINING_RE.search(msg) and not _TOP_PRODUCTS_RE.search(msg):
        args = _period_args_from_message(msg, start_date, end_date)
        args.update({"days": extract_period_args(msg).get("days", 30), "limit": 5})
        plans.append(ToolPlan(
            tool_name="get_declining_products",
            args=args,
            reason="declining products",
        ))
        return plans

    if _KPI_COMPARISON_RE.search(msg):
        args = _period_args_from_message(msg, start_date, end_date)
        plans.append(ToolPlan(
            tool_name="get_supplier_kpis",
            args=args,
            reason="period comparison",
        ))
        return plans

    if _TOP_PRODUCTS_RE.search(msg) and not _DECLINING_RE.search(msg):
        region = extract_region(msg)
        args = _period_args_from_message(msg, start_date, end_date)
        if region:
            args["region"] = region
        args["limit"] = resolve_product_ranking_limit(
            msg,
            is_ytd=is_current_year_phrase(msg),
        )
        plans.append(ToolPlan(
            tool_name="get_top_products",
            args=args,
            reason=f"top products{f' ({region})' if region else ''}",
        ))
        return plans

    if _MARKET_SHARE_RE.search(msg):
        category = extract_category(msg) or default_category_for_supplier(supplier_name)
        args = _period_args_from_message(msg, start_date, end_date)
        args["category_name"] = category
        plans.append(ToolPlan(
            tool_name="get_market_share",
            args=args,
            reason=f"market share ({category})",
        ))
        return plans

    return plans


def prior_context_from_dict(data: Optional[dict]) -> Optional[PriorTurnContext]:
    if not data or not isinstance(data, dict):
        return None
    question = (data.get("question") or "").strip()
    if not question:
        return None
    tool_calls = tuple(data.get("tool_calls") or [])
    sources = tuple(data.get("sources") or [])
    return PriorTurnContext(
        question=question,
        answer=data.get("answer") or "",
        tool_calls=tool_calls,
        sources=sources,
        has_chart=bool(data.get("has_chart")),
    )
