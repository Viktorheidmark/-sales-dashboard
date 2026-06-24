"""
Structured follow-up context — preserves normalized analysis period across chip actions.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Optional

from app.services.period_labels import infer_period_kind
from app.services.period_utils import align_weekly_query_bounds, resolve_period_range, is_current_year_phrase, current_year_period_range, default_data_bounds
from app.services.ranking_limits import resolve_product_ranking_limit

# ---------------------------------------------------------------------------
# Patterns for natural-language context follow-up detection
# ---------------------------------------------------------------------------

_NL_NEW_SUBJECT_RE = re.compile(
    r"(marknadsandel|konkurrent|fokusera|välj\s+kategori|"
    r"hur\s+har\s+(?:total|hela\s+företaget)|visa\s+(?:alla|samtliga)\s+produkter|"
    r"hur\s+går\s+det\s+totalt|vilken\s+produkt|vilken\s+region)",
    re.IGNORECASE,
)

# Patterns for detecting sentence-level (standalone) questions that must NOT be
# treated as follow-up modifiers even when they contain modifier words like "top 3"
# or a region name.
_STANDALONE_QUESTION_RE = re.compile(
    r"("
    r"vilka?\s|"           # "vilken / vilka produkter..."
    r"hur\s+stor|"         # "hur stor marknadsandel..."
    r"hur\s+går\s+det|"    # "hur går det..."
    r"hur\s+har\s+|"       # "hur har försäljningen..."
    r"ge\s+mig\s|"         # "ge mig top 3..."
    r"berätta\s|"          # "berätta om..."
    r"vad\s+är\s|"         # "vad är..."
    r"visa\s+v[aå]r[ae]\s|"# "visa våra starkaste..."
    r"säljer\s+bäst|"      # "...säljer bäst..."
    r"genererar\s+mest|"   # "...genererar mest..."
    r"\.{0}produkterna\b"  # "...produkterna" (noun form = full sentence)
    r")",
    re.IGNORECASE,
)

_NL_GRANULARITY_WEEK_RE = re.compile(
    r"(vecka\s+för\s+vecka|per\s+vecka|visa\s+per\s+vecka|visa\s+vecka\s+för\s+vecka)",
    re.IGNORECASE,
)

# Tight patterns: only match when the ENTIRE message is a bare modifier phrase.
# These prevent standalone sentences that happen to contain "top 3" or a city name
# from being misclassified as follow-up modifiers.
_BARE_LIMIT_RE = re.compile(
    r"^(?:top|topp)\s+(\d{1,2})\s*(?:då\s*)?\??\s*$",
    re.IGNORECASE,
)

from app.services.intent_router import KNOWN_REGIONS as _KNOWN_REGIONS_FOR_RE
_BARE_REGION_RE = re.compile(
    r"^i\s+(" + "|".join(re.escape(r) for r in _KNOWN_REGIONS_FOR_RE) + r")\s*(?:då\s*)?\??\s*$",
    re.IGNORECASE,
)

_PRIOR_INTENTS_ELIGIBLE = frozenset({
    "product_ranking",
    "sales_trend",
    "sales_overview",
    "region_ranking",
    "market_share",
    "product_decline",
    "revenue_drivers",
})

_NL_TOOL_FOR_INTENT = {
    "product_ranking": "get_top_products",
    "sales_trend": "get_sales_over_time",
    "sales_overview": "get_supplier_kpis",
    "region_ranking": "get_sales_by_region",
    "market_share": "get_market_share",
    "product_decline": "get_declining_products",
    "revenue_drivers": "get_revenue_drivers",
}

ALLOWED_FOLLOW_UP_ACTIONS = frozenset({
    "weekly_trend",
    "region_breakdown",
    "product_drivers",
    "yoy_compare",
    "period_change",
    "region_filter",
    "product_trend",
})

_TOOL_PRIORITY = (
    "get_supplier_kpis",
    "get_sales_over_time",
    "get_top_products",
    "get_sales_by_region",
    "get_revenue_drivers",
    "get_market_share",
    "get_declining_products",
)


@dataclass
class AnalysisContext:
    prior_intent: str = ""
    start_date: str = ""
    end_date: str = ""
    period_kind: str = ""
    granularity: str = ""
    region: Optional[str] = None
    category: Optional[str] = None
    product_name: Optional[str] = None
    limit: Optional[int] = None
    prior_tool_calls: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v not in (None, "", [])}

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Optional["AnalysisContext"]:
        if not data or not isinstance(data, dict):
            return None
        start = str(data.get("start_date") or "")[:10]
        end = str(data.get("end_date") or "")[:10]
        if not start or not end:
            return None
        return cls(
            prior_intent=str(data.get("prior_intent") or ""),
            start_date=start,
            end_date=end,
            period_kind=str(data.get("period_kind") or ""),
            granularity=str(data.get("granularity") or ""),
            region=data.get("region"),
            category=data.get("category"),
            product_name=data.get("product_name"),
            limit=data.get("limit"),
            prior_tool_calls=list(data.get("prior_tool_calls") or []),
        )


def _best_date_range(by_tool: dict[str, dict]) -> tuple[str, str]:
    sales = by_tool.get("get_sales_over_time") or {}
    qdr = sales.get("query_date_range") or {}
    if qdr.get("start") and qdr.get("end"):
        return str(qdr["start"])[:10], str(qdr["end"])[:10]

    for name in _TOOL_PRIORITY:
        result = by_tool.get(name) or {}
        dr = result.get("date_range") or {}
        if dr.get("start") and dr.get("end"):
            return str(dr["start"])[:10], str(dr["end"])[:10]
    return "", ""


def _infer_prior_intent(by_tool: dict[str, dict], question: str = "") -> str:
    if "get_supplier_kpis" in by_tool and "get_sales_over_time" in by_tool:
        return "sales_overview"
    if "get_sales_over_time" in by_tool:
        return "sales_trend"
    if "get_top_products" in by_tool:
        return "product_ranking"
    if "get_sales_by_region" in by_tool:
        return "region_ranking"
    if "get_revenue_drivers" in by_tool:
        return "revenue_drivers"
    if "get_market_share" in by_tool:
        return "market_share"
    return "unknown"


def extract_analysis_context(
    tool_results: list[tuple[str, dict]],
    question: str = "",
) -> dict[str, Any]:
    """Build server-side analysis context from verified tool output."""
    by_tool: dict[str, dict] = {}
    for name, result in tool_results:
        if isinstance(result, dict) and "error" not in result:
            by_tool[name] = result

    start, end = _best_date_range(by_tool)
    if not start or not end:
        return {}

    period_kind = ""
    for name in _TOOL_PRIORITY:
        pk = (by_tool.get(name) or {}).get("_period_kind")
        if pk:
            period_kind = str(pk)
            break
    if not period_kind:
        period_kind = infer_period_kind(
            {"start": start, "end": end},
            message=question,
        )

    sales = by_tool.get("get_sales_over_time") or {}
    top = by_tool.get("get_top_products") or {}
    ms = by_tool.get("get_market_share") or {}

    ctx = AnalysisContext(
        prior_intent=_infer_prior_intent(by_tool, question),
        start_date=start,
        end_date=end,
        period_kind=period_kind,
        granularity=str(sales.get("granularity") or ""),
        region=top.get("region_filter"),
        category=ms.get("category_name"),
        limit=top.get("limit"),
        prior_tool_calls=[name for name, _ in tool_results if isinstance(_, dict)],
    )
    products = top.get("products") or []
    if products and products[0].get("product_name"):
        ctx.product_name = str(products[0]["product_name"])
    return ctx.to_dict()


def _align_weekly_args(args: dict) -> dict:
    if args.get("granularity") != "week":
        return args
    start_s = args.get("start_date")
    end_s = args.get("end_date")
    if not start_s or not end_s:
        return args
    aligned = align_weekly_query_bounds(str(start_s), str(end_s))
    out = dict(args)
    out["start_date"] = aligned["start"]
    out["end_date"] = aligned["end"]
    return out


def analysis_context_from_prior_data(
    question: str,
    tool_calls: list[str] | tuple[str, ...],
    sources: list | tuple,
    analysis_context: Optional[dict] = None,
) -> Optional[AnalysisContext]:
    if analysis_context:
        ctx = AnalysisContext.from_dict(analysis_context)
        if ctx:
            ctx.prior_tool_calls = list(tool_calls)
        return ctx
    pseudo_results = []
    for s in sources:
        if isinstance(s, dict) and s.get("tool"):
            pseudo_results.append((s["tool"], {"date_range": s.get("date_range") or {}}))
    ctx_dict = extract_analysis_context(pseudo_results, question)
    if not ctx_dict:
        for source in sources:
            if not isinstance(source, dict):
                continue
            dr = source.get("date_range") or {}
            if dr.get("start") and dr.get("end"):
                return AnalysisContext(
                    start_date=str(dr["start"])[:10],
                    end_date=str(dr["end"])[:10],
                    period_kind=infer_period_kind(dr, message=question),
                    prior_tool_calls=list(tool_calls),
                    prior_intent="unknown",
                )
        return None
    ctx = AnalysisContext.from_dict(ctx_dict)
    if ctx:
        ctx.prior_tool_calls = list(tool_calls)
    return ctx


def _span_days(ctx: AnalysisContext) -> int:
    try:
        start = date.fromisoformat(ctx.start_date[:10])
        end = date.fromisoformat(ctx.end_date[:10])
        return (end - start).days + 1
    except ValueError:
        return 0


def _base_period_args(ctx: AnalysisContext) -> dict:
    args: dict[str, Any] = {
        "start_date": ctx.start_date,
        "end_date": ctx.end_date,
        "_period_kind": ctx.period_kind or infer_period_kind(
            {"start": ctx.start_date, "end": ctx.end_date},
        ),
        "_period_explicit": True,
    }
    if ctx.start_date:
        args["_requested_start_date"] = ctx.start_date
    return args


def plan_from_analysis_context(
    action_type: str,
    ctx: AnalysisContext,
    *,
    message: str = "",
    supplier_name: str = "",
) -> list:
    from app.services.intent_router import ToolPlan, default_category_for_supplier, extract_period_args, extract_region

    if action_type not in ALLOWED_FOLLOW_UP_ACTIONS:
        return []

    if action_type == "period_change":
        period_args = extract_period_args(message)
        if not period_args.get("start_date") or not period_args.get("end_date"):
            return []
        args = {
            "start_date": period_args["start_date"],
            "end_date": period_args["end_date"],
            "_period_kind": period_args.get("period_kind")
            or infer_period_kind(
                {"start": period_args["start_date"], "end": period_args["end_date"]},
                message=message,
            ),
            "_period_explicit": True,
        }
        primary = next((t for t in _TOOL_PRIORITY if t in ctx.prior_tool_calls), "get_sales_over_time")
        if primary == "get_top_products":
            args["limit"] = ctx.limit or resolve_product_ranking_limit(
                message,
                is_ytd=period_args.get("period_kind") == "current_year",
            )
            if ctx.region:
                args["region"] = ctx.region
        elif primary == "get_sales_over_time":
            args["granularity"] = ctx.granularity or "month"
            args["_chart_intent"] = "time_series"
            args["_force_time_series"] = True
            args = _align_weekly_args(args)
        elif primary == "get_market_share":
            args["category_name"] = ctx.category or default_category_for_supplier(supplier_name)
        return [ToolPlan(primary, args, reason=f"period-change follow-up ({primary})")]

    if action_type == "region_filter":
        region = extract_region(message)
        if not region:
            return []
        args = _base_period_args(ctx)
        args["region"] = region
        primary = next((t for t in _TOOL_PRIORITY if t in ctx.prior_tool_calls), "get_top_products")
        if primary == "get_top_products":
            args["limit"] = ctx.limit or resolve_product_ranking_limit(
                message,
                is_ytd=ctx.period_kind in ("year_to_date", "current_year"),
            )
            return [ToolPlan("get_top_products", args, reason="region-filter follow-up")]
        if primary == "get_sales_by_region":
            return [ToolPlan("get_sales_by_region", args, reason="region-filter follow-up")]
        args["limit"] = resolve_product_ranking_limit(message, is_ytd=False)
        return [ToolPlan("get_top_products", args, reason="region-filter follow-up")]

    args = _base_period_args(ctx)

    if action_type == "weekly_trend":
        args.update({
            "granularity": "week",
            "_chart_intent": "time_series",
            "_force_time_series": True,
        })
        args = _align_weekly_args(args)
        return [ToolPlan("get_sales_over_time", args, reason="weekly-trend follow-up")]

    if action_type == "region_breakdown":
        return [ToolPlan("get_sales_by_region", args, reason="region-breakdown follow-up")]

    if action_type == "product_drivers":
        span = _span_days(ctx)
        if span > 90 or ctx.period_kind in ("year_to_date", "current_year"):
            args["limit"] = ctx.limit or resolve_product_ranking_limit(
                message,
                is_ytd=ctx.period_kind in ("year_to_date", "current_year"),
            )
            if ctx.region:
                args["region"] = ctx.region
            return [ToolPlan("get_top_products", args, reason="product-drivers follow-up (ranking)")]
        days = min(max(span, 7), 365)
        return [ToolPlan(
            "get_revenue_drivers",
            {"days": days, "limit": 5, "_chart_intent": "drivers_data"},
            reason="product-drivers follow-up",
        )]

    if action_type == "yoy_compare":
        return [ToolPlan("get_supplier_kpis", args, reason="yoy-compare follow-up")]

    if action_type == "product_trend":
        args.update({
            "granularity": "month" if _span_days(ctx) > 90 else "week",
            "_chart_intent": "time_series",
            "_force_time_series": True,
        })
        args = _align_weekly_args(args)
        return [ToolPlan("get_sales_over_time", args, reason="product-trend follow-up")]

    return []


def validate_and_resolve_follow_up(
    follow_up_action: Optional[dict],
    prior_question: str,
    prior_tool_calls: list[str] | tuple[str, ...],
    prior_sources: list | tuple,
    prior_analysis_context: Optional[dict],
    *,
    message: str = "",
    supplier_name: str = "",
) -> list:
    """Validate structured follow-up payload; never trust client dates over prior context."""
    if not follow_up_action or not prior_question:
        return []

    action_type = str(follow_up_action.get("action") or "").strip()
    if action_type not in ALLOWED_FOLLOW_UP_ACTIONS:
        return []

    ctx = analysis_context_from_prior_data(
        prior_question,
        prior_tool_calls,
        prior_sources,
        prior_analysis_context,
    )
    if not ctx or not ctx.start_date or not ctx.end_date:
        return []

    # Period replacement is explicit — only period_change may use message-resolved dates.
    if action_type != "period_change":
        client_ctx = follow_up_action.get("context") or {}
        if isinstance(client_ctx, dict):
            if client_ctx.get("region"):
                ctx.region = str(client_ctx["region"])
            if client_ctx.get("product_name"):
                ctx.product_name = str(client_ctx["product_name"])

    plans = plan_from_analysis_context(
        action_type,
        ctx,
        message=message,
        supplier_name=supplier_name,
    )
    if not plans:
        return []

    # UI defaults must not override preserved follow-up dates (except period_change).
    if action_type != "period_change":
        for plan in plans:
            if plan.args.get("start_date") and plan.args.get("end_date"):
                continue
            plan.args["start_date"] = ctx.start_date
            plan.args["end_date"] = ctx.end_date

    return plans


def _nl_resolve_new_period(msg: str) -> Optional[dict]:
    """Resolve a new period from a short NL message. Returns period dict or None."""
    today = date.today()
    # Full history first (most specific pattern)
    if re.search(r"(?:över\s+)?hela\s+period[ae]n|all\s+tillgänglig|all\s+tid\b", msg, re.IGNORECASE):
        data_min, data_max = default_data_bounds(today)
        return {
            "start_date": data_min.isoformat(),
            "end_date": data_max.isoformat(),
            "_period_kind": "full_history",
            "_period_explicit": True,
        }
    # Previous year
    if re.search(r"förra\s+år[ae]t|föregående\s+år[ae]t|förra\s+kalenderåret", msg, re.IGNORECASE):
        data_min, data_max = default_data_bounds(today)
        year = today.year - 1
        start = max(date(year, 1, 1), data_min)
        end = min(date(year, 12, 31), data_max)
        return {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "_period_kind": "previous_year",
            "_period_explicit": True,
        }
    # Current year / YTD (including "hela året", "i år")
    if is_current_year_phrase(msg):
        ytd = current_year_period_range(today)
        return {
            "start_date": ytd["start_date"],
            "end_date": ytd["end_date"],
            "_period_kind": "year_to_date",
            "_period_explicit": True,
        }
    # General phrase resolution (senaste X dag, senaste veckan, etc.)
    period = resolve_period_range(msg)
    if period.get("start_date") and period.get("end_date"):
        return {
            "start_date": period["start_date"],
            "end_date": period["end_date"],
            "_period_kind": period.get("period_kind", "phrase_resolved"),
            "_period_explicit": True,
        }
    return None


def _nl_apply_period_to_intent(ctx: AnalysisContext, new_period: dict, supplier_name: str) -> list:
    """Build tool plans applying new_period to the prior intent."""
    from app.services.intent_router import ToolPlan, default_category_for_supplier

    intent = ctx.prior_intent

    if intent == "product_ranking":
        args: dict[str, Any] = {**new_period, "limit": ctx.limit or 5}
        if ctx.region:
            args["region"] = ctx.region
        if ctx.category:
            args["category_name"] = ctx.category
        return [ToolPlan("get_top_products", args, reason="nl-context: period → product_ranking")]

    if intent == "sales_trend":
        span = 0
        try:
            span = (date.fromisoformat(new_period["end_date"]) - date.fromisoformat(new_period["start_date"])).days + 1
        except (ValueError, KeyError):
            pass
        granularity = ctx.granularity or ("month" if span > 90 else "week")
        args = {
            **new_period,
            "granularity": granularity,
            "_chart_intent": "time_series",
            "_force_time_series": True,
        }
        args = _align_weekly_args(args)
        return [ToolPlan("get_sales_over_time", args, reason="nl-context: period → sales_trend")]

    if intent == "sales_overview":
        kpi_args: dict[str, Any] = dict(new_period)
        trend_args: dict[str, Any] = {
            **new_period,
            "granularity": "month",
            "_chart_intent": "time_series",
            "_force_time_series": True,
        }
        return [
            ToolPlan("get_supplier_kpis", kpi_args, reason="nl-context: period → sales_overview KPIs"),
            ToolPlan("get_sales_over_time", trend_args, reason="nl-context: period → sales_overview trend"),
        ]

    if intent == "region_ranking":
        return [ToolPlan("get_sales_by_region", dict(new_period), reason="nl-context: period → region_ranking")]

    if intent == "market_share":
        args = dict(new_period)
        if ctx.category:
            args["category_name"] = ctx.category
        else:
            args["category_name"] = default_category_for_supplier(supplier_name)
        return [ToolPlan("get_market_share", args, reason="nl-context: period → market_share")]

    if intent == "product_decline":
        try:
            days = (date.fromisoformat(new_period["end_date"]) - date.fromisoformat(new_period["start_date"])).days + 1
        except (ValueError, KeyError):
            days = 30
        return [ToolPlan("get_declining_products", {"days": min(days, 90), "limit": 5}, reason="nl-context: period → product_decline")]

    return []


def plan_nl_context_followup(
    message: str,
    ctx: AnalysisContext,
    supplier_name: str = "",
) -> list:
    """
    Detect NL modifier phrases (period/region/limit/granularity) and apply them
    to the prior analysis context. Returns [] when the message is not a modifier.

    Safety: supplier_id is never read here; all dates clamped by default_data_bounds;
    only runs when prior intent is in the eligible set; rejects new-subject queries.
    """
    from app.services.intent_router import ToolPlan, extract_region

    if not ctx or not ctx.start_date or not ctx.end_date:
        return []
    if ctx.prior_intent not in _PRIOR_INTENTS_ELIGIBLE:
        return []

    msg = message.strip()

    # Reject messages that look like full standalone questions (sentence structure).
    # These must go through the normal planner, not be treated as modifiers.
    if _STANDALONE_QUESTION_RE.search(msg):
        return []

    # Reject long messages (anything > 60 chars is almost certainly a new question)
    if len(msg) > 60:
        return []

    # Reject messages that introduce a new analysis subject
    if _NL_NEW_SUBJECT_RE.search(msg):
        return []

    # 1. Granularity change: "visa vecka för vecka"
    if _NL_GRANULARITY_WEEK_RE.search(msg):
        if ctx.prior_intent in ("sales_trend", "sales_overview"):
            args: dict[str, Any] = {
                "start_date": ctx.start_date,
                "end_date": ctx.end_date,
                "_period_kind": ctx.period_kind or "preserved",
                "_period_explicit": True,
                "granularity": "week",
                "_chart_intent": "time_series",
                "_force_time_series": True,
            }
            args = _align_weekly_args(args)
            return [ToolPlan("get_sales_over_time", args, reason="nl-context: granularity → weekly")]
        return []

    # 2. Limit change: only when the ENTIRE message is a bare "top N [då?]" phrase.
    bare_limit = _BARE_LIMIT_RE.match(msg)
    if bare_limit and ctx.prior_intent == "product_ranking":
        limit = int(bare_limit.group(1))
        if 1 <= limit <= 25:
            args = {
                "start_date": ctx.start_date,
                "end_date": ctx.end_date,
                "_period_kind": ctx.period_kind or "preserved",
                "_period_explicit": True,
                "limit": limit,
            }
            if ctx.region:
                args["region"] = ctx.region
            if ctx.category:
                args["category_name"] = ctx.category
            return [ToolPlan("get_top_products", args, reason=f"nl-context: limit → {limit}")]

    # 3. Region filter: only when the ENTIRE message is a bare "i <Region> [då?]" phrase.
    bare_region = _BARE_REGION_RE.match(msg)
    if bare_region:
        region = next(
            (r for r in _KNOWN_REGIONS_FOR_RE if r.lower() == bare_region.group(1).lower()),
            bare_region.group(1),
        )
        from app.services.intent_router import extract_region as _er
        return plan_from_analysis_context("region_filter", ctx, message=f"i {region}", supplier_name=supplier_name)

    # 4. Period change
    new_period = _nl_resolve_new_period(msg)
    if new_period:
        return _nl_apply_period_to_intent(ctx, new_period, supplier_name)

    return []


def make_follow_up_action(
    label: str,
    message: str,
    action: str,
    ctx: dict[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "label": label,
        "message": message,
        "action": action,
    }
    if ctx:
        payload["context"] = {
            k: ctx[k]
            for k in ("start_date", "end_date", "period_kind", "granularity", "region", "category")
            if ctx.get(k)
        }
    return payload
