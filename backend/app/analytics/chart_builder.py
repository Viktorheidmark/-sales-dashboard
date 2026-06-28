"""
Chart builder — produces a chart payload from the canonical ``AnalysisResult``,
never from loosely interpreted user text.

Every payload embeds plan identity (``analysis_plan_id``, ``intent``, ``metric``,
``period_a``, ``period_b``) so the frontend / verifier can reject payloads whose
periods do not match the response. Negative changes stay semantically red
regardless of tenant.
"""

from __future__ import annotations

from typing import Any, Optional

from app.analytics.labels import readable_range
from app.analytics.schemas import AnalysisResult


def build_chart_payload(result: AnalysisResult, tenant_theme: Optional[dict] = None) -> Optional[dict[str, Any]]:
    """Build the chart payload for a result, or None when no chart applies."""
    plan = result.resolved_plan
    if plan.chart_intent == "none":
        return None
    if plan.intent == "period_comparison":
        return _comparison_bar(result, tenant_theme or {})
    return None


def _comparison_bar(result: AnalysisResult, tenant_theme: dict) -> dict[str, Any]:
    spec = result.resolved_plan.comparison
    assert spec is not None
    cur = result.kpis.get("current", {})
    pri = result.kpis.get("prior", {})
    metric = result.kpis.get("metric", "revenue")

    period_a = spec.period_a
    period_b = spec.period_b

    prior_value = float(pri.get(metric, pri.get("revenue", 0.0)) or 0.0)
    current_value = float(cur.get(metric, cur.get("revenue", 0.0)) or 0.0)
    negative = current_value < prior_value

    # Readable Swedish labels — never raw ISO on the axis.
    period_a_label = readable_range(period_a)
    period_b_label = readable_range(period_b)

    # Baseline first (Period A), analyzed second (Period B) — matches plan order.
    data = [
        {
            "label": period_a_label,
            "period_phase": "prior",
            "revenue": prior_value,
            "period": period_a.to_iso_dict(),
        },
        {
            "label": period_b_label,
            "period_phase": "latest",
            "revenue": current_value,
            "period": period_b.to_iso_dict(),
        },
    ]

    return {
        "chart_type": "bar_chart",
        "chart_variant": "period_comparison",
        "x_key": "label",
        "y_key": "revenue",
        "data": data,
        "title": "Jämförelse mellan perioder",
        "description": _description(result),
        "period_note": f"{period_b_label} jämfört med {period_a_label}",
        "source_tool": "get_supplier_kpis",
        "generated_from_row_count": 2,
        "emphasis_index": 1,
        "negative_change": negative,
        # --- plan identity (verified against the response) ---
        "analysis_plan_id": result.plan_id,
        "intent": result.resolved_plan.intent,
        "metric": metric,
        "period_a": period_a.to_iso_dict(),
        "period_b": period_b.to_iso_dict(),
        "period_a_label": period_a_label,
        "period_b_label": period_b_label,
        "comparison_type": spec.comparison_type,
        "tenant_theme": tenant_theme,
    }


def _description(result: AnalysisResult) -> str:
    delta = result.kpis.get("delta", {})
    pct = delta.get("revenue_pct")
    if pct is None:
        return "Omsättning per period."
    sign = "+" if pct >= 0 else ""
    return f"Förändring i omsättning: {sign}{pct} %."
