"""
Hybrid tool planning: deterministic secure paths → AI planner → legacy regex fallback.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional

from app.schemas.analysis_plan import AnalysisPlan, NormalizedPlanMeta
from app.services.intent_router import (
    PriorTurnContext,
    ToolPlan,
    _YTD_WEEKLY_RE,
    extract_period_args,
    extract_region,
    is_diagram_followup_request,
    plan_forced_tools,
    plan_deep_dive_followup_tools,
    plan_comparison_followup_tools,
    plan_period_followup_tools,
    plan_long_term_trend_tools,
    plan_followup_tools,
)
from app.services.plan_normalizer import normalize_plan
from app.services.planner_service import call_planner


def _use_ai_planner() -> bool:
    return os.environ.get("USE_AI_PLANNER", "true").lower() in ("1", "true", "yes")


@dataclass
class ToolResolution:
    plans: list[ToolPlan] = field(default_factory=list)
    source: str = "none"
    analysis_meta: dict[str, Any] = field(default_factory=dict)
    clarification_answer: Optional[str] = None


def plan_deterministic_tools(
    message: str,
    supplier_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    prior_context: Optional[PriorTurnContext] = None,
    follow_up_action: Optional[dict] = None,
) -> list[ToolPlan]:
    """Secure follow-ups and UI actions — always bypass the AI planner."""
    msg = message.strip()

    if follow_up_action:
        from app.services.decline_period import (
            DECLINE_PERIOD_ACTION,
            plan_decline_period_from_action,
        )
        if str(follow_up_action.get("action") or "").strip() == DECLINE_PERIOD_ACTION:
            structured_decline = plan_decline_period_from_action(follow_up_action)
            if structured_decline:
                return structured_decline

    if prior_context:
        from app.services.decline_period import (
            plan_awaiting_decline_period,
            prior_awaiting_decline_period,
        )
        if prior_awaiting_decline_period(prior_context):
            awaiting = plan_awaiting_decline_period(msg)
            if awaiting:
                return awaiting

    if prior_context and follow_up_action:
        from app.services.follow_up_context import validate_and_resolve_follow_up
        structured = validate_and_resolve_follow_up(
            follow_up_action,
            prior_context.question,
            list(prior_context.tool_calls),
            list(prior_context.sources),
            prior_context.analysis_context,
            message=msg,
            supplier_name=supplier_name,
        )
        if structured:
            return structured

    if prior_context:
        from app.services.follow_up_context import (
            analysis_context_from_prior_data,
            plan_from_analysis_context,
            plan_nl_context_followup,
        )
        ctx = analysis_context_from_prior_data(
            prior_context.question,
            list(prior_context.tool_calls),
            list(prior_context.sources),
            prior_context.analysis_context,
        )
        if ctx:
            nl_plans = plan_nl_context_followup(msg, ctx, supplier_name=supplier_name)
            if nl_plans:
                return nl_plans
        if ctx and _YTD_WEEKLY_RE.search(msg) and not extract_period_args(msg):
            weekly = plan_from_analysis_context("weekly_trend", ctx, message=msg, supplier_name=supplier_name)
            if weekly:
                return weekly
        if ctx and extract_region(msg) and len(msg) <= 24:
            region_only = plan_from_analysis_context(
                "region_filter", ctx, message=msg, supplier_name=supplier_name,
            )
            if region_only:
                return region_only

    if prior_context:
        for planner_fn in (
            plan_comparison_followup_tools,
            plan_deep_dive_followup_tools,
            plan_period_followup_tools,
            plan_long_term_trend_tools,
            plan_followup_tools,
        ):
            plans = planner_fn(msg, prior_context, supplier_name, start_date, end_date)
            if plans:
                return plans
    if is_diagram_followup_request(msg):
        return []
    return []


def resolve_tool_plans(
    message: str,
    supplier_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    prior_context: Optional[PriorTurnContext] = None,
    follow_up_action: Optional[dict] = None,
    *,
    planner_client: Any = None,
    planner_model: Optional[str] = None,
    injected_plan: Optional[AnalysisPlan] = None,
) -> ToolResolution:
    """
    Resolve MCP tool plans for a user message.

    injected_plan: for unit tests — skip OpenAI and use this plan directly.
    """
    meta: dict[str, Any] = {"ui_default_range": {"start": start_date, "end": end_date}}

    det = plan_deterministic_tools(
        message, supplier_name, start_date, end_date, prior_context, follow_up_action,
    )
    if det:
        meta.update({"source": "deterministic", "tools": [p.tool_name for p in det]})
        return ToolResolution(plans=det, source="deterministic", analysis_meta=meta)

    from app.services.comparison_labels import (
        COMPARISON_PERIOD_CLARIFICATION,
        comparison_needs_period_clarification,
    )
    from app.services.decline_period import prior_awaiting_decline_period
    if not prior_awaiting_decline_period(prior_context):
        if comparison_needs_period_clarification(message, prior_context):
            meta.update({"source": "clarification", "intent": "period_comparison"})
            return ToolResolution(
                clarification_answer=COMPARISON_PERIOD_CLARIFICATION,
                source="clarification",
                analysis_meta=meta,
            )

    from app.services.decline_period import (
        DECLINE_PERIOD_CLARIFICATION,
        decline_question_needs_period,
    )
    if decline_question_needs_period(message):
        meta.update({"source": "clarification", "intent": "product_decline"})
        return ToolResolution(
            clarification_answer=DECLINE_PERIOD_CLARIFICATION,
            source="clarification",
            analysis_meta=meta,
        )

    if _use_ai_planner():
        try:
            plan = injected_plan or call_planner(
                message,
                supplier_name,
                prior=prior_context,
                client=planner_client,
                model=planner_model,
            )
            meta["planner_raw"] = plan.model_dump()
            normalized = normalize_plan(
                plan,
                message,
                supplier_name,
                ui_start=start_date,
                ui_end=end_date,
                prior=prior_context,
            )
            if normalized.meta:
                meta["normalized"] = normalized.meta.model_dump()
            if normalized.clarification_answer:
                meta.update({"source": "clarification", "intent": "product_decline"})
                return ToolResolution(
                    clarification_answer=normalized.clarification_answer,
                    source="clarification",
                    analysis_meta=meta,
                )
            if not normalized.use_fallback and normalized.tool_plans:
                meta.update({
                    "source": "planner",
                    "tools": [p.tool_name for p in normalized.tool_plans],
                })
                return ToolResolution(
                    plans=normalized.tool_plans,
                    source="planner",
                    analysis_meta=meta,
                )
            meta["planner_fallback_reason"] = "low_confidence_or_unsupported"
        except Exception as exc:
            meta["planner_error"] = str(exc)

    legacy = plan_forced_tools(
        message, supplier_name, start_date, end_date, prior_context=prior_context,
    )
    if legacy:
        meta.update({
            "source": "legacy_fallback",
            "tools": [p.tool_name for p in legacy],
        })
        return ToolResolution(plans=legacy, source="legacy_fallback", analysis_meta=meta)

    meta["source"] = "llm_tools"
    return ToolResolution(plans=[], source="llm_tools", analysis_meta=meta)
