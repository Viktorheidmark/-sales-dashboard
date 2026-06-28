"""
Verification agent — runs after data execution and before response generation.

For the comparison capability verification is **deterministic and structural**:
the dangerous failures this guards against (a chart period that differs from the
plan period, a metric mismatch, a tenant-scope mismatch, a custom comparison
silently described as "latest N days") are all exactly checkable. A deterministic
verifier is strictly more reliable than asking a model "do these dates match",
and it is fully testable. A semantic LLM check can be layered on top in a later
phase without changing this contract.

The verifier compares the plan, the canonical result, and the proposed chart
payload, and returns a structured ``VerificationResult``.
"""

from __future__ import annotations

from typing import Any, Optional

from app.analytics.schemas import AnalysisPlan, AnalysisResult, VerificationResult


def _iso(period) -> Optional[dict]:
    return period.to_iso_dict() if period is not None else None


def verify(
    plan: AnalysisPlan,
    result: AnalysisResult,
    chart_payload: Optional[dict[str, Any]],
    *,
    expected_supplier_id: str,
    expected_tenant_id: str,
) -> VerificationResult:
    issues: list[str] = []

    # --- scope ---
    scope_ok = (
        result.supplier_id == expected_supplier_id
        and result.tenant_id == expected_tenant_id
    )
    if not scope_ok:
        issues.append("Tenant/supplier scope mismatch between result and authenticated context.")

    # --- result periods must equal plan periods exactly ---
    periods_ok = True
    if plan.comparison is not None:
        pa = plan.comparison.period_a
        pb = plan.comparison.period_b
        if result.comparison_period is None or (
            result.comparison_period.start != pa.start or result.comparison_period.end != pa.end
        ):
            periods_ok = False
            issues.append("Result comparison_period (Period A) does not match plan.")
        if result.primary_period is None or (
            result.primary_period.start != pb.start or result.primary_period.end != pb.end
        ):
            periods_ok = False
            issues.append("Result primary_period (Period B) does not match plan.")

    # --- metric ---
    plan_metric = plan.metric or "revenue"
    result_metric = result.kpis.get("metric", plan_metric)
    metric_ok = result_metric == plan_metric
    if not metric_ok:
        issues.append(f"Metric mismatch: plan='{plan_metric}', result='{result_metric}'.")

    # --- chart must match plan + result periods, intent, metric ---
    chart_ok = True
    if plan.chart_intent != "none":
        if chart_payload is None:
            chart_ok = False
            issues.append("Plan expects a chart but none was produced.")
        else:
            if chart_payload.get("analysis_plan_id") != result.plan_id:
                chart_ok = False
                issues.append("Chart plan id does not match result plan id.")
            if chart_payload.get("intent") != plan.intent:
                chart_ok = False
                issues.append("Chart intent does not match plan intent.")
            if chart_payload.get("metric") != plan_metric:
                chart_ok = False
                issues.append("Chart metric does not match plan metric.")
            if plan.comparison is not None:
                if chart_payload.get("period_a") != _iso(plan.comparison.period_a):
                    chart_ok = False
                    issues.append("Chart Period A does not match plan Period A.")
                if chart_payload.get("period_b") != _iso(plan.comparison.period_b):
                    chart_ok = False
                    issues.append("Chart Period B does not match plan Period B.")
                # Guard against a custom comparison mislabeled as a rolling window.
                if (
                    plan.comparison.comparison_type != "rolling"
                    and chart_payload.get("comparison_type") == "rolling"
                ):
                    chart_ok = False
                    issues.append("Custom comparison mislabeled as rolling in chart.")

    approved = scope_ok and periods_ok and metric_ok and chart_ok
    if approved:
        return VerificationResult(
            approved=True,
            severity="none",
            issues=[],
            required_action="continue",
            verified_periods_match=periods_ok,
            verified_metric_match=metric_ok,
            verified_chart_match=chart_ok,
            verified_scope_match=scope_ok,
        )

    # Period / scope / chart mismatches are blocking. Open the composer rather
    # than render a mixed analysis.
    return VerificationResult(
        approved=False,
        severity="blocking",
        issues=issues,
        required_action="clarify",
        verified_periods_match=periods_ok,
        verified_metric_match=metric_ok,
        verified_chart_match=chart_ok,
        verified_scope_match=scope_ok,
    )
