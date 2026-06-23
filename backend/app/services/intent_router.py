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

from app.services.period_utils import align_weekly_query_bounds, completed_week_bounds

CATEGORIES = ("Mejeri", "Dryck", "Mat och snacks")
KNOWN_REGIONS = ("Stockholm", "Göteborg", "Malmö", "Uppsala", "Online")

CHART_TOOL_PRIORITY = [
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

_KPI_COMPARISON_RE = re.compile(
    r"(föregående period|jämfört med förra|mot föregående|periodjämförelse|periodöversikt)",
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
})


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
    if "coca-cola" in name or "cocacola" in name:
        return "Dryck"
    if "orkla" in name:
        return "Mat och snacks"
    return "Mejeri"


def extract_category(message: str) -> Optional[str]:
    msg = message.lower()
    if "mat och snacks" in msg:
        return "Mat och snacks"
    if "mejeri" in msg:
        return "Mejeri"
    if "dryck" in msg:
        return "Dryck"
    if re.search(r"\bsnacks\b", msg):
        return "Mat och snacks"
    return None


def extract_region(message: str) -> Optional[str]:
    for region in KNOWN_REGIONS:
        if region.lower() in message.lower():
            return region
    return None


def is_diagram_followup_request(message: str) -> bool:
    return bool(_DIAGRAM_FOLLOWUP_RE.search(message.strip()))


def is_period_only_followup(message: str) -> bool:
    msg = message.strip()
    if not msg or _SUBJECT_CHANGE_RE.search(msg):
        return False
    return bool(_PERIOD_ONLY_FOLLOWUP_RE.match(msg))


def extract_period_args(message: str, reference: Optional[date] = None) -> dict:
    """Derive start_date/end_date (and optional days) from relative Swedish period phrases."""
    today = reference or date.today()
    msg = message.lower()

    match = re.search(r"senaste\s+(\d+)\s+dag", msg)
    if match:
        days = int(match.group(1))
        return {
            "start_date": (today - timedelta(days=days)).isoformat(),
            "end_date": today.isoformat(),
            "days": days,
        }

    if re.search(r"senaste\s+veck", msg):
        week_start, week_end = completed_week_bounds(today)
        days = (week_end - week_start).days + 1
        return {
            "start_date": week_start.isoformat(),
            "end_date": week_end.isoformat(),
            "days": days,
            "completed_week": True,
        }

    if re.search(r"senaste\s+90", msg):
        days = 90
        return {
            "start_date": (today - timedelta(days=days)).isoformat(),
            "end_date": today.isoformat(),
            "days": days,
        }

    if re.search(r"senaste\s+180", msg):
        days = 180
        return {
            "start_date": (today - timedelta(days=days)).isoformat(),
            "end_date": today.isoformat(),
            "days": days,
        }

    return {}


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
        args["limit"] = 5
    elif tool_name == "get_declining_products":
        args["days"] = period_args.get("days", 30)
        args["limit"] = 5
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
        period_followup = plan_period_followup_tools(
            msg, prior_context, supplier_name, start_date, end_date,
        )
        if period_followup:
            return period_followup
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

    if _SALES_TREND_RE.search(msg):
        period_args = extract_period_args(msg)
        args = period_args if period_args else _date_args(start_date, end_date)
        args["granularity"] = _granularity_from_date_range(
            args.get("start_date"),
            args.get("end_date"),
            msg,
        )
        if _WEEKLY_SALES_RE.search(msg) and period_args.get("completed_week"):
            week_start, week_end = completed_week_bounds()
            args["start_date"] = week_start.isoformat()
            args["end_date"] = week_end.isoformat()
        args = _align_sales_over_time_weekly(args)
        if _WEEKLY_SALES_RE.search(msg) and period_args.get("completed_week"):
            args = _ensure_chartable_sales_window(args, msg)
        plans.append(ToolPlan(
            tool_name="get_sales_over_time",
            args=args,
            reason="sales trend",
        ))
        return plans

    if _SALES_BY_REGION_RE.search(msg) and not _TOP_PRODUCTS_RE.search(msg):
        args = _date_args(start_date, end_date)
        plans.append(ToolPlan(
            tool_name="get_sales_by_region",
            args=args,
            reason="regional sales comparison",
        ))
        return plans

    if _DECLINING_RE.search(msg) and not _TOP_PRODUCTS_RE.search(msg):
        args = _date_args(start_date, end_date)
        args.update({"days": 30, "limit": 5})
        plans.append(ToolPlan(
            tool_name="get_declining_products",
            args=args,
            reason="declining products",
        ))
        return plans

    if _KPI_COMPARISON_RE.search(msg):
        args = _date_args(start_date, end_date)
        plans.append(ToolPlan(
            tool_name="get_supplier_kpis",
            args=args,
            reason="period comparison",
        ))
        return plans

    if _TOP_PRODUCTS_RE.search(msg):
        region = extract_region(msg)
        if region:
            args = _date_args(start_date, end_date)
            args["region"] = region
            args["limit"] = 5
            plans.append(ToolPlan(
                tool_name="get_top_products",
                args=args,
                reason=f"regional top products ({region})",
            ))
            return plans

    if _MARKET_SHARE_RE.search(msg):
        category = extract_category(msg) or default_category_for_supplier(supplier_name)
        args = _date_args(start_date, end_date)
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
