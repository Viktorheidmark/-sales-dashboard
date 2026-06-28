"""
Query executor — maps a validated plan into typed tool inputs and normalizes
the output into one canonical ``AnalysisResult``.

The executor takes an injectable async ``tool_runner`` so it can be unit-tested
without a live MCP/DB session. In production the runner is bound to the MCP
session and injects tenant scope at the boundary (``supplier_id`` is never taken
from plan content).

For ``period_comparison`` the executor calls ``get_supplier_kpis`` once per exact
period (Period B = analyzed/current, Period A = baseline) and carries those exact
ranges through unchanged. There is no rolling/365 fallback.
"""

from __future__ import annotations

import uuid
from typing import Awaitable, Callable

from app.analytics.schemas import AnalysisPlan, AnalysisResult, DateRange

# A runner executes a registered tool with typed args and returns its raw dict.
# Tenant scope is applied inside the runner, not here.
ToolRunner = Callable[[str, dict], Awaitable[dict]]


def _num(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _pct_change(current: float, prior: float) -> float | None:
    if prior == 0:
        return None
    return round((current - prior) / prior * 100.0, 1)


async def execute_plan(
    plan: AnalysisPlan,
    *,
    tenant_id: str,
    supplier_id: str,
    tool_runner: ToolRunner,
    plan_id: str | None = None,
) -> AnalysisResult:
    """Execute a validated plan and return a canonical AnalysisResult."""
    pid = plan_id or uuid.uuid4().hex

    if plan.intent == "period_comparison":
        return await _execute_comparison(
            plan, tenant_id=tenant_id, supplier_id=supplier_id,
            tool_runner=tool_runner, plan_id=pid,
        )

    raise ValueError(f"Executor does not (yet) support intent '{plan.intent}'.")


async def _execute_comparison(
    plan: AnalysisPlan,
    *,
    tenant_id: str,
    supplier_id: str,
    tool_runner: ToolRunner,
    plan_id: str,
) -> AnalysisResult:
    spec = plan.comparison
    assert spec is not None  # guaranteed by validator

    period_a = spec.period_a  # baseline
    period_b = spec.period_b  # analyzed / current

    # Exact dates flow straight into the tool — no inference.
    b_kpi = await tool_runner(
        "get_supplier_kpis",
        {"start_date": period_b.start.isoformat(), "end_date": period_b.end.isoformat()},
    )
    a_kpi = await tool_runner(
        "get_supplier_kpis",
        {"start_date": period_a.start.isoformat(), "end_date": period_a.end.isoformat()},
    )

    warnings: list[str] = []
    for label, kpi in (("Period A", a_kpi), ("Period B", b_kpi)):
        if isinstance(kpi, dict) and kpi.get("error"):
            warnings.append(f"{label}: {kpi['error']}")

    cur_rev, pri_rev = _num(b_kpi.get("total_revenue")), _num(a_kpi.get("total_revenue"))
    cur_ord, pri_ord = _num(b_kpi.get("total_orders")), _num(a_kpi.get("total_orders"))
    cur_unt, pri_unt = _num(b_kpi.get("total_units")), _num(a_kpi.get("total_units"))
    cur_aov, pri_aov = _num(b_kpi.get("average_order_value")), _num(a_kpi.get("average_order_value"))

    kpis = {
        "metric": plan.metric or "revenue",
        "current": {
            "period": period_b.to_iso_dict(),
            "revenue": cur_rev, "orders": cur_ord, "units": cur_unt, "average_order_value": cur_aov,
        },
        "prior": {
            "period": period_a.to_iso_dict(),
            "revenue": pri_rev, "orders": pri_ord, "units": pri_unt, "average_order_value": pri_aov,
        },
        "delta": {
            "revenue_abs": round(cur_rev - pri_rev, 2),
            "revenue_pct": _pct_change(cur_rev, pri_rev),
            "orders_abs": round(cur_ord - pri_ord, 2),
            "units_abs": round(cur_unt - pri_unt, 2),
        },
        "comparison_type": spec.comparison_type,
        "comparison_source": spec.source,
    }

    if pri_rev <= 0:
        warnings.append("Baselineperioden saknar omsättning – procentuell förändring visas inte.")

    return AnalysisResult(
        plan_id=plan_id,
        tenant_id=tenant_id,
        supplier_id=supplier_id,
        resolved_plan=plan,
        primary_period=period_b,
        comparison_period=period_a,
        kpis=kpis,
        chart_data=None,  # built by chart_builder, then verified
        warnings=warnings,
        source_tools=["get_supplier_kpis"],
    )
