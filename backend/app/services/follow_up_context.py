"""
Structured follow-up context — preserves normalized analysis period across chip actions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Optional

from app.services.period_labels import infer_period_kind
from app.services.period_utils import align_weekly_query_bounds
from app.services.ranking_limits import resolve_product_ranking_limit

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
