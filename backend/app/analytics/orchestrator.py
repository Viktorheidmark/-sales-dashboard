"""
Orchestrator — wires the canonical analytics stages for migrated capabilities.

    plan → validate → execute → build chart → verify → respond

Returns an ``OrchestratorOutcome`` telling the caller (chat.py) exactly what to
do: render the answer, open the in-chat comparison composer, or defer to the
legacy pipeline. The orchestrator only handles capabilities listed in
``registry.MIGRATED_CAPABILITIES`` (initially: explicit period comparison);
everything else returns ``defer`` so existing behavior is preserved.

A structured, secret-free trace is attached for observability/debugging.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from app.analytics import chart_builder, executor, planner, responder, verifier
from app.analytics.executor import ToolRunner
from app.analytics.registry import is_migrated
from app.analytics.validator import validate_plan

OutcomeKind = Literal["answer", "clarify_composer", "clarify_text", "defer", "blocked", "execute"]


@dataclass
class OrchestratorOutcome:
    kind: OutcomeKind
    payload: Optional[dict[str, Any]] = None
    trace: dict[str, Any] = field(default_factory=dict)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def comparison_precheck(
    message: str,
    *,
    follow_up_action: Optional[dict] = None,
    request_id: Optional[str] = None,
    tenant_id: str = "",
):
    """Cheap, MCP-free decision: plan + validate only.

    Returns ``(outcome, plan)`` where ``outcome.kind`` is one of:
      * ``defer`` — not a migrated comparison; caller uses the legacy pipeline.
      * ``clarify_composer`` — comparison intent without two valid periods.
      * ``execute`` — caller must run the full pipeline with a tool runner.

    No tool/MCP/DB access happens here, so the common non-comparison case never
    pays the cost of spawning the MCP subprocess.
    """
    rid = request_id or uuid.uuid4().hex
    trace: dict[str, Any] = {"request_id": rid, "tenant_id": tenant_id, "stage": "planner"}

    plan = planner.plan_comparison(message, follow_up_action=follow_up_action)
    if plan is None:
        trace["result"] = "defer_not_comparison"
        return OrchestratorOutcome(kind="defer", trace=trace), None

    if not is_migrated(plan.intent) and plan.intent != "clarification":
        trace["result"] = "defer_not_migrated"
        return OrchestratorOutcome(kind="defer", trace=trace), plan

    trace.update(
        intent=plan.intent,
        chart_intent=plan.chart_intent,
        comparison_type=(plan.comparison.comparison_type if plan.comparison else None),
        period_a=(plan.comparison.period_a.to_iso_dict() if plan.comparison else None),
        period_b=(plan.comparison.period_b.to_iso_dict() if plan.comparison else None),
        planner_confidence=plan.confidence,
    )

    trace["stage"] = "validator"
    outcome = validate_plan(plan)
    trace["validation_approved"] = outcome.approved
    if outcome.issues:
        trace["validation_issues"] = list(outcome.issues)

    if not outcome.approved:
        clarification_type = outcome.clarification_type or plan.clarification_type or "comparison_dates"
        if clarification_type == "comparison_dimension":
            trace["result"] = "clarify_dimension"
            return OrchestratorOutcome(kind="clarify_text", trace=trace), plan
        # Comparison-date clarification (or any block) → open the composer; no tools.
        trace["result"] = (
            "clarify_composer"
            if clarification_type == "comparison_dates"
            else "blocked_validation"
        )
        return OrchestratorOutcome(kind="clarify_composer", trace=trace), plan

    trace["result"] = "execute"
    return OrchestratorOutcome(kind="execute", trace=trace), plan


async def orchestrate_comparison(
    message: str,
    *,
    supplier_id: str,
    supplier_name: str,
    tool_runner: ToolRunner,
    follow_up_action: Optional[dict] = None,
    tenant_theme: Optional[dict] = None,
    request_id: Optional[str] = None,
) -> OrchestratorOutcome:
    """Run the comparison capability end-to-end behind the canonical pipeline."""
    rid = request_id or uuid.uuid4().hex
    tenant_id = supplier_id  # supplier scope is the tenant boundary in this app

    # 1-2. Plan + validate (MCP-free) ----------------------------------------
    pre, plan = comparison_precheck(
        message, follow_up_action=follow_up_action, request_id=rid, tenant_id=tenant_id,
    )
    if pre.kind != "execute":
        return pre
    assert plan is not None
    trace = pre.trace

    plan_id = uuid.uuid4().hex
    trace["plan_id"] = plan_id

    # 3. Execute --------------------------------------------------------------
    trace["stage"] = "executor"
    result = await executor.execute_plan(
        plan, tenant_id=tenant_id, supplier_id=supplier_id,
        tool_runner=tool_runner, plan_id=plan_id,
    )
    trace["source_tools"] = list(result.source_tools)
    if result.warnings:
        trace["warnings"] = list(result.warnings)

    # 4. Chart ----------------------------------------------------------------
    trace["stage"] = "chart"
    chart_payload = chart_builder.build_chart_payload(result, tenant_theme=tenant_theme)
    result.chart_data = chart_payload

    # 5. Verify ---------------------------------------------------------------
    trace["stage"] = "verifier"
    verdict = verifier.verify(
        plan, result, chart_payload,
        expected_supplier_id=supplier_id, expected_tenant_id=tenant_id,
    )
    trace["verifier_approved"] = verdict.approved
    trace["verifier_severity"] = verdict.severity
    if verdict.issues:
        trace["verifier_issues"] = list(verdict.issues)

    if not verdict.approved:
        # Blocking mismatch: never render a mixed analysis. Open the composer.
        trace["result"] = "blocked_verifier"
        return OrchestratorOutcome(kind="clarify_composer", trace=trace)

    # 6. Respond --------------------------------------------------------------
    trace["stage"] = "responder"
    answer = responder.render_answer(result)
    trace["result"] = "answer"

    payload = _build_chat_payload(answer, result, chart_payload, supplier_id)
    return OrchestratorOutcome(kind="answer", payload=payload, trace=trace)


def _build_chat_payload(
    answer: str,
    result,
    chart_payload: Optional[dict],
    supplier_id: str,
) -> dict[str, Any]:
    from app.analytics.labels import readable_range

    spec = result.resolved_plan.comparison
    period_a_label = readable_range(spec.period_a) if spec else None
    period_b_label = readable_range(spec.period_b) if spec else None
    comparison_label = (
        f"{period_b_label} jämfört med {period_a_label}"
        if period_a_label and period_b_label
        else None
    )
    sources = [
        {
            "tool": "get_supplier_kpis",
            "supplier_id": supplier_id,
            "date_range": result.primary_period.to_iso_dict() if result.primary_period else None,
            "comparison_period": result.comparison_period.to_iso_dict() if result.comparison_period else None,
            "comparison_period_label": comparison_label,
        }
    ]
    analysis_context = {
        "prior_intent": "period_comparison",
        "comparison_type": spec.comparison_type if spec else None,
        "period_a": spec.period_a.to_iso_dict() if spec else None,
        "period_b": spec.period_b.to_iso_dict() if spec else None,
        "period_a_label": period_a_label,
        "period_b_label": period_b_label,
    }
    # Invariant: one analysis result → one primary chart. The chart lives ONLY in
    # `chart`; `charts` (additional charts) is empty so the frontend never renders
    # the same comparison bar twice.
    return {
        "answer": answer,
        "tool_calls": list(result.source_tools),
        "sources": sources,
        "chart": chart_payload,
        "charts": [],
        "deep_dive": None,
        "follow_up_actions": [],
        "analysis_context": analysis_context,
        "limitations": list(result.warnings),
        "supplier_id": supplier_id,
        "generated_at": _now_iso(),
        "response_kind": "conversational",
    }
