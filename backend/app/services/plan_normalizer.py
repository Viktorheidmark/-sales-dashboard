"""
Deterministic validation and normalization of AI planner output.

The normalizer has final authority over dates, tenant scope, tools, chart hints,
and security constraints. It never reads supplier_id from the planner.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from app.schemas.analysis_plan import AnalysisPlan, NormalizedPlanMeta
from app.services.intent_router import (
    KNOWN_REGIONS,
    CATEGORIES,
    ToolPlan,
    default_category_for_supplier,
    extract_region,
    plan_forced_tools,
)
from app.services.intent_router import PriorTurnContext as RouterPriorContext
from app.services.ranking_limits import extract_ranking_limit, resolve_product_ranking_limit
from app.services.period_labels import message_specifies_period
from app.services.period_utils import (
    completed_week_bounds,
    default_data_bounds,
    default_decline_comparison_days,
    is_current_year_phrase,
    resolve_period_range,
)

ALLOWED_TOOLS = frozenset({
    "get_supplier_kpis",
    "get_sales_over_time",
    "get_top_products",
    "get_sales_by_region",
    "get_market_share",
    "get_declining_products",
    "get_revenue_drivers",
})

CONFIDENCE_THRESHOLD = 0.45
_CORE_INTENTS = frozenset({
    "sales_overview",
    "sales_trend",
    "product_ranking",
    "market_share",
    "product_decline",
    "region_ranking",
    "portfolio_change",
})

_REGION_FOLLOWUP_RE = re.compile(
    r"^\s*i\s+(" + "|".join(re.escape(r) for r in KNOWN_REGIONS) + r")\s*\??\s*$",
    re.IGNORECASE,
)

_PRIOR_INTENT_FROM_TOOLS = {
    "get_top_products": "product_ranking",
    "get_sales_over_time": "sales_trend",
    "get_supplier_kpis": "sales_overview",
    "get_market_share": "market_share",
    "get_declining_products": "product_decline",
    "get_sales_by_region": "region_ranking",
    "get_revenue_drivers": "portfolio_change",
}


@dataclass
class NormalizedPlan:
    tool_plans: list[ToolPlan] = field(default_factory=list)
    use_fallback: bool = False
    meta: Optional[NormalizedPlanMeta] = None
    raw_plan: Optional[dict[str, Any]] = None


def _infer_intent_from_prior(prior: RouterPriorContext) -> str:
    for tool in prior.tool_calls:
        if tool in _PRIOR_INTENT_FROM_TOOLS:
            return _PRIOR_INTENT_FROM_TOOLS[tool]
    return "sales_trend"


def _apply_followup_overrides(
    message: str,
    plan: AnalysisPlan,
    prior: Optional[RouterPriorContext],
) -> AnalysisPlan:
    if not prior:
        return plan

    region_match = _REGION_FOLLOWUP_RE.match(message.strip())
    if region_match:
        region = next(
            (r for r in KNOWN_REGIONS if r.lower() == region_match.group(1).lower()),
            region_match.group(1),
        )
        prior_intent = _infer_intent_from_prior(prior)
        filters = plan.filters.model_copy(update={"regions": [region]})
        return plan.model_copy(update={
            "intent": prior_intent,  # type: ignore[arg-type]
            "filters": filters,
            "confidence": max(plan.confidence, 0.85),
            "clarification_needed": False,
        })

    return plan


def _resolve_period(
    plan: AnalysisPlan,
    message: str,
    ui_start: Optional[str],
    ui_end: Optional[str],
    reference: Optional[date] = None,
) -> tuple[str, str, str, list[str]]:
    """Return (start_date, end_date, period_kind, notes)."""
    notes: list[str] = []
    today = reference or datetime.now(tz=timezone.utc).date()
    data_min, data_max = default_data_bounds(today)
    tp = plan.time_period

    phrase = resolve_period_range(message, reference=today, data_min=data_min, data_max=data_max)
    if phrase.get("start_date") and phrase.get("end_date"):
        kind = phrase.get("period_kind", "phrase_resolved")
        return phrase["start_date"], phrase["end_date"], str(kind), notes

    if is_current_year_phrase(message):
        from app.services.period_utils import current_year_period_range
        resolved = current_year_period_range(today, data_min, data_max)
        return resolved["start_date"], resolved["end_date"], "year_to_date", notes

    if tp.kind == "full_history":
        return data_min.isoformat(), data_max.isoformat(), "full_history", notes

    if tp.kind == "previous_completed_week" and re.search(r"senaste\s+veck", message, re.I):
        week_start, week_end = completed_week_bounds(today)
        return week_start.isoformat(), week_end.isoformat(), "previous_completed_week", notes

    if tp.kind == "exact_range" and tp.start_date and tp.end_date and message_specifies_period(message):
        try:
            start_d = date.fromisoformat(tp.start_date[:10])
            end_d = date.fromisoformat(tp.end_date[:10])
            start_d = max(start_d, data_min)
            end_d = min(end_d, data_max)
            if start_d > end_d:
                start_d = end_d
            return start_d.isoformat(), end_d.isoformat(), "exact_range", notes
        except ValueError:
            notes.append("invalid exact_range clamped via message fallback")

    # Ignore planner rolling defaults when the user did not name a period.
    if tp.kind in ("rolling_days", "rolling_months", "year_to_date", "previous_year", "current_week"):
        notes.append(f"planner {tp.kind} ignored — no explicit period in question")

    notes.append("no explicit period → full history default")
    return data_min.isoformat(), data_max.isoformat(), "full_history", notes


def _validate_region(region: Optional[str]) -> Optional[str]:
    if not region:
        return None
    for known in KNOWN_REGIONS:
        if known.lower() == region.lower():
            return known
    return None


def _validate_category(category: Optional[str], supplier_name: str) -> str:
    if category:
        for cat in CATEGORIES:
            if cat.lower() == category.lower():
                return cat
    return default_category_for_supplier(supplier_name)


def _granularity_for(
    plan: AnalysisPlan,
    start_date: str,
    end_date: str,
    period_kind: str,
) -> str:
    viz = plan.visualization.granularity
    if viz != "auto":
        return viz

    if period_kind == "year_to_date":
        return "month"
    if period_kind in ("previous_completed_week", "current_week"):
        return "week"

    try:
        span = (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days + 1
        if span <= 14:
            return "day"
        if span <= 90:
            return "week"
        return "month"
    except ValueError:
        return "month"


def _chart_intent_for(plan: AnalysisPlan) -> Optional[str]:
    viz = plan.visualization.primary
    if viz in ("line", "area"):
        return "time_series"
    if viz == "bar_compare":
        return "period_comparison"
    if viz == "bar_ranked":
        return None
    if plan.intent in ("sales_trend", "sales_overview", "region_trend"):
        return "time_series"
    if plan.intent == "portfolio_change" and plan.comparison.kind == "previous_period":
        return "period_comparison"
    return None


def _build_tool_plans(
    plan: AnalysisPlan,
    *,
    message: str,
    start_date: str,
    end_date: str,
    period_kind: str,
    granularity: str,
    region: Optional[str],
    category: str,
    chart_intent: Optional[str],
) -> list[ToolPlan]:
    intent = plan.intent
    base = {
        "start_date": start_date,
        "end_date": end_date,
        "_period_kind": period_kind,
        "_period_explicit": period_kind not in ("ui_default", "safe_fallback"),
    }
    plans: list[ToolPlan] = []

    if intent == "sales_overview":
        plans.append(ToolPlan("get_supplier_kpis", dict(base), reason="planner: YTD/overview KPIs"))
        trend_args = {
            **base,
            "granularity": granularity,
            "_chart_intent": chart_intent or "time_series",
            "_force_time_series": True,
        }
        plans.append(ToolPlan("get_sales_over_time", trend_args, reason="planner: overview trend"))
        return plans

    if intent == "sales_trend":
        trend_args = {
            **base,
            "granularity": granularity,
            "_chart_intent": chart_intent or "time_series",
            "_force_time_series": True,
        }
        plans.append(ToolPlan("get_sales_over_time", trend_args, reason="planner: sales trend"))
        if plan.needs_deep_dive:
            days = max(7, (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days + 1)
            plans.append(ToolPlan(
                "get_revenue_drivers",
                {"days": min(days, 90), "limit": 5, "_chart_intent": "drivers_data"},
                reason="planner: trend drivers",
            ))
        return plans

    if intent == "product_ranking":
        is_ytd = period_kind == "year_to_date" or plan.time_period.kind == "year_to_date"
        limit = resolve_product_ranking_limit(
            message,
            plan_limit=plan.limit,
            is_ytd=is_ytd,
        )
        args = {**base, "limit": limit}
        if region:
            args["region"] = region
        plans.append(ToolPlan("get_top_products", args, reason="planner: product ranking"))
        return plans

    if intent == "region_ranking":
        plans.append(ToolPlan("get_sales_by_region", dict(base), reason="planner: region ranking"))
        return plans

    if intent == "market_share":
        plans.append(ToolPlan(
            "get_market_share",
            {**base, "category_name": category},
            reason="planner: market share",
        ))
        return plans

    if intent == "product_decline":
        explicit = message_specifies_period(message)
        if explicit:
            days = int(
                plan.time_period.days
                or resolve_period_range(message).get("days")
                or 30
            )
        else:
            days = default_decline_comparison_days()
        plans.append(ToolPlan(
            "get_declining_products",
            {
                "days": min(days, 365),
                "limit": 5,
                "_period_kind": "full_history_halves" if not explicit else f"rolling_{days}",
            },
            reason="planner: product decline",
        ))
        return plans

    if intent == "portfolio_change":
        days = plan.time_period.days or max(
            7, (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days + 1,
        )
        plans.append(ToolPlan(
            "get_revenue_drivers",
            {"days": min(days, 90), "limit": 5, "_chart_intent": "period_comparison"},
            reason="planner: portfolio change",
        ))
        return plans

    return []


def normalize_plan(
    plan: AnalysisPlan,
    message: str,
    supplier_name: str,
    ui_start: Optional[str] = None,
    ui_end: Optional[str] = None,
    prior: Optional[RouterPriorContext] = None,
    reference: Optional[date] = None,
) -> NormalizedPlan:
    """Validate planner output and produce executable tool plans."""
    notes: list[str] = []
    plan = _apply_followup_overrides(message, plan, prior)

    if plan.clarification_needed and plan.confidence < CONFIDENCE_THRESHOLD:
        return NormalizedPlan(use_fallback=True, raw_plan=plan.model_dump())

    intent = plan.intent
    if intent == "unknown" or intent not in _CORE_INTENTS:
        if is_current_year_phrase(message) and re.search(r"överlag|hur\s+ser", message, re.I):
            plan = plan.model_copy(update={"intent": "sales_overview", "confidence": 0.8})
            intent = "sales_overview"
            notes.append("inferred sales_overview from YTD overview phrasing")
        elif is_current_year_phrase(message) and re.search(r"utvecklats|utveckling", message, re.I):
            plan = plan.model_copy(update={"intent": "sales_trend", "confidence": 0.8})
            intent = "sales_trend"
            notes.append("inferred sales_trend from YTD development phrasing")
        elif is_current_year_phrase(message) and re.search(r"produkt|bäst|topp", message, re.I):
            update: dict = {"intent": "product_ranking", "confidence": 0.8}
            explicit = extract_ranking_limit(message)
            if explicit is not None:
                update["limit"] = explicit
            plan = plan.model_copy(update=update)
            intent = "product_ranking"
            notes.append("inferred product_ranking from YTD product phrasing")
        elif plan.confidence < CONFIDENCE_THRESHOLD:
            return NormalizedPlan(use_fallback=True, raw_plan=plan.model_dump())

    start_date, end_date, period_kind, period_notes = _resolve_period(
        plan, message, ui_start, ui_end, reference=reference,
    )
    notes.extend(period_notes)

    region = _validate_region(
        plan.filters.regions[0] if plan.filters.regions else extract_region(message),
    )
    if plan.filters.category:
        category = _validate_category(plan.filters.category, supplier_name)
    elif "läsk" in message.lower():
        category = "Läsk"
    elif "chips" in message.lower() or "snacks" in message.lower():
        category = "Chips & snacks"
    else:
        category = _validate_category(None, supplier_name)

    granularity = _granularity_for(plan, start_date, end_date, period_kind)
    chart_intent = _chart_intent_for(plan)

    tool_plans = _build_tool_plans(
        plan,
        message=message,
        start_date=start_date,
        end_date=end_date,
        period_kind=period_kind,
        granularity=granularity,
        region=region,
        category=category,
        chart_intent=chart_intent,
    )

    for tp in tool_plans:
        if tp.tool_name not in ALLOWED_TOOLS:
            return NormalizedPlan(use_fallback=True, raw_plan=plan.model_dump())

    if not tool_plans:
        return NormalizedPlan(use_fallback=True, raw_plan=plan.model_dump())

    meta = NormalizedPlanMeta(
        intent=plan.intent,
        resolved_start_date=start_date,
        resolved_end_date=end_date,
        period_kind=period_kind,
        tools=[p.tool_name for p in tool_plans],
        granularity=granularity,
        chart_intent=chart_intent,
        region=region,
        category=category,
        planner_confidence=plan.confidence,
        normalization_notes=notes,
    )
    return NormalizedPlan(tool_plans=tool_plans, meta=meta, raw_plan=plan.model_dump())


def normalize_without_planner(
    message: str,
    supplier_name: str,
    ui_start: Optional[str] = None,
    ui_end: Optional[str] = None,
    prior: Optional[RouterPriorContext] = None,
) -> NormalizedPlan:
    """Build normalized meta from legacy deterministic routing (for tests/fallback)."""
    legacy = plan_forced_tools(message, supplier_name, ui_start, ui_end, prior_context=prior)
    if not legacy:
        return NormalizedPlan(use_fallback=True)
    start = legacy[0].args.get("start_date", ui_start or "")
    end = legacy[0].args.get("end_date", ui_end or "")
    return NormalizedPlan(
        tool_plans=legacy,
        meta=NormalizedPlanMeta(
            intent="unknown",
            resolved_start_date=str(start),
            resolved_end_date=str(end),
            period_kind="legacy",
            tools=[p.tool_name for p in legacy],
            granularity=legacy[0].args.get("granularity", "auto"),
            planner_confidence=1.0,
            normalization_notes=["legacy deterministic routing"],
        ),
    )
