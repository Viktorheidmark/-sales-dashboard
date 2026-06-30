"""Regression tests for comparison-dimension resolution before date composer."""

import os
import unittest
from unittest.mock import patch

from app.analytics.orchestrator import comparison_precheck
from app.analytics import planner as analytics_planner
from app.services.comparison_labels import (
    COMPARISON_DIMENSION_CLARIFICATION,
    COMPARISON_TWO_PERIODS_CLARIFICATION,
    classify_comparison_dimension,
    comparison_needs_dimension_clarification,
    comparison_needs_period_clarification,
    is_product_extremes_comparison,
)
from app.services.intent_router import plan_forced_tools
from app.services.tool_planner import resolve_tool_plans


SUPPLIER = "Coca-Cola Europacific Partners Sverige"
UI_START = "2026-03-25"
UI_END = "2026-06-23"


def _routing_decision(message: str) -> dict:
    """Summarize the deterministic routing outcome for a fresh-chat message."""
    dim = classify_comparison_dimension(message)
    plan = analytics_planner.plan_comparison(message)
    pre, _ = comparison_precheck(message, tenant_id="tenant-test")
    forced = plan_forced_tools(message, SUPPLIER, UI_START, UI_END)
    with patch.dict(os.environ, {"USE_AI_PLANNER": "false"}):
        resolution = resolve_tool_plans(message, SUPPLIER, UI_START, UI_END)

    if pre.kind == "clarify_text":
        route = "dimension_clarification"
    elif pre.kind == "clarify_composer":
        route = "period_composer"
    elif pre.kind == "execute":
        route = "period_comparison_execute"
    elif pre.kind == "defer" and forced:
        tool = forced[0].tool_name
        chart = forced[0].args.get("_chart_intent")
        if chart == "product_extremes":
            route = "product_extremes"
        elif chart == "period_comparison":
            route = "period_comparison_legacy"
        else:
            route = f"legacy:{tool}"
    elif resolution.clarification_answer:
        route = f"clarification:{resolution.analysis_meta.get('intent')}"
    else:
        route = pre.kind

    return {
        "message": message,
        "dimension": dim,
        "route": route,
        "orchestrator": pre.kind,
        "plan_intent": plan.intent if plan else None,
        "plan_clarification": plan.clarification_type if plan else None,
        "forced_tools": [p.tool_name for p in forced],
        "forced_chart_intent": forced[0].args.get("_chart_intent") if forced else None,
        "resolution_source": resolution.source,
        "resolution_clarification": resolution.clarification_answer,
    }


class ComparisonDimensionRoutingTests(unittest.TestCase):
    def setUp(self):
        self._orch_patch = patch.dict(
            os.environ,
            {"AI_ORCHESTRATED_ANALYTICS_ENABLED": "true", "USE_AI_PLANNER": "false"},
        )
        self._orch_patch.start()

    def tearDown(self):
        self._orch_patch.stop()

    def test_product_extremes_short_phrase(self):
        message = "jämför bästa och sämsta produkten"
        self.assertTrue(is_product_extremes_comparison(message))
        decision = _routing_decision(message)
        self.assertEqual(decision["dimension"], "product")
        self.assertEqual(decision["route"], "product_extremes")
        self.assertEqual(decision["forced_tools"], ["get_top_products"])
        self.assertEqual(decision["forced_chart_intent"], "product_extremes")
        self.assertFalse(comparison_needs_period_clarification(message))
        self.assertFalse(comparison_needs_dimension_clarification(message))
        self.assertIsNone(analytics_planner.plan_comparison(message))

    def test_product_extremes_long_phrase(self):
        message = (
            "kan du visa en jämförelse mellan den produkten som går bäst "
            "och den som går sämst"
        )
        decision = _routing_decision(message)
        self.assertEqual(decision["dimension"], "product")
        self.assertEqual(decision["route"], "product_extremes")
        self.assertEqual(decision["orchestrator"], "defer")
        self.assertIsNone(analytics_planner.plan_comparison(message))

        with patch.dict(os.environ, {"USE_AI_PLANNER": "true"}):
            res = resolve_tool_plans(message, SUPPLIER, UI_START, UI_END)
        self.assertEqual(res.source, "legacy_fallback")
        self.assertEqual(len(res.plans), 1)
        self.assertEqual(res.plans[0].tool_name, "get_top_products")
        self.assertEqual(res.plans[0].args.get("_chart_intent"), "product_extremes")

    def test_product_extremes_chart_wins_over_kpi_period_comparison(self):
        from app.services.chart_policy import resolve_chart_intent, select_charts

        message = (
            "kan du visa en jämförelse mellan den produkten som går bäst "
            "och den som går sämst"
        )
        products = {
            "_chart_intent": "product_extremes",
            "products": [
                {"product_name": "Strong", "revenue": 5000.0},
                {"product_name": "Weak", "revenue": 200.0},
            ],
            "date_range": {"start": "2024-06-30", "end": "2026-06-29"},
        }
        kpi = {
            "_chart_intent": "period_comparison",
            "total_revenue": 5_000_000.0,
            "prev_total_revenue": 4_000_000.0,
            "date_range": {"start": "2024-06-30", "end": "2026-06-29"},
            "prev_date_range": {"start": "2023-06-30", "end": "2024-06-29"},
        }
        raw = [("get_supplier_kpis", kpi), ("get_top_products", products)]
        self.assertEqual(resolve_chart_intent(message, raw).value, "product_extremes")
        charts = select_charts(message, raw)
        self.assertEqual(charts[0]["title"], "Bästa vs sämsta produkt")
        self.assertEqual(charts[0]["chart_variant"], "product_comparison")
        self.assertNotEqual(charts[0]["title"], "Periodjämförelse")

    def test_explicit_month_period_comparison(self):
        message = "jämför mars med februari"
        decision = _routing_decision(message)
        self.assertEqual(decision["dimension"], "period")
        self.assertEqual(decision["route"], "period_comparison_execute")
        self.assertEqual(decision["plan_intent"], "period_comparison")

    def test_explicit_rolling_period_comparison(self):
        message = "jämför senaste 30 dagarna med föregående 30 dagar"
        decision = _routing_decision(message)
        self.assertEqual(decision["dimension"], "period")
        self.assertEqual(decision["route"], "period_comparison_execute")
        self.assertEqual(decision["forced_tools"], ["get_revenue_drivers"])

    def test_vague_comparison_dimension_clarification(self):
        message = "kan du göra en jämförelse?"
        decision = _routing_decision(message)
        self.assertEqual(decision["dimension"], "ambiguous")
        self.assertEqual(decision["route"], "dimension_clarification")
        self.assertEqual(decision["plan_clarification"], "comparison_dimension")
        self.assertTrue(comparison_needs_dimension_clarification(message))

        with patch.dict(os.environ, {"USE_AI_PLANNER": "false"}):
            res = resolve_tool_plans(message, SUPPLIER, UI_START, UI_END)
        self.assertEqual(res.source, "clarification")
        self.assertEqual(res.analysis_meta.get("intent"), "comparison_dimension")
        self.assertEqual(res.clarification_answer, COMPARISON_DIMENSION_CLARIFICATION)
        self.assertEqual(res.plans, [])

    def test_time_period_choice_opens_composer_not_dimension(self):
        message = "jag vill jämföra två tidsperioder"
        decision = _routing_decision(message)
        self.assertEqual(decision["dimension"], "period")
        self.assertEqual(decision["route"], "period_composer")
        self.assertTrue(comparison_needs_period_clarification(message))
        self.assertFalse(comparison_needs_dimension_clarification(message))

        with patch.dict(os.environ, {"USE_AI_PLANNER": "false"}):
            res = resolve_tool_plans(message, SUPPLIER, UI_START, UI_END)
        self.assertEqual(res.source, "clarification")
        self.assertEqual(res.analysis_meta.get("intent"), "period_comparison")
        self.assertEqual(res.clarification_answer, COMPARISON_TWO_PERIODS_CLARIFICATION)

    def test_explicit_day_month_ranges_execute(self):
        message = "mellan 1–8 mars och 9–18 mars"
        spec = analytics_planner.parse_explicit_comparison(message)
        self.assertIsNotNone(spec)
        self.assertEqual(spec.period_a.start.day, 1)
        self.assertEqual(spec.period_a.end.day, 8)
        self.assertEqual(spec.period_b.start.day, 9)
        self.assertEqual(spec.period_b.end.day, 18)

        decision = _routing_decision(message)
        self.assertEqual(decision["dimension"], "period")
        self.assertEqual(decision["route"], "period_comparison_execute")

    def test_routing_table_for_review(self):
        """Emit exact routing decisions for all required regression phrases."""
        cases = {
            "jämför bästa och sämsta produkten": "product_extremes",
            "kan du visa en jämförelse mellan den produkten som går bäst och den som går sämst": "product_extremes",
            "jämför mars med februari": "period_comparison_execute",
            "jämför senaste 30 dagarna med föregående 30 dagar": "period_comparison_execute",
            "kan du göra en jämförelse?": "dimension_clarification",
            "jag vill jämföra två tidsperioder": "period_composer",
            "mellan 1–8 mars och 9–18 mars": "period_comparison_execute",
        }
        for message, expected_route in cases.items():
            with self.subTest(message=message):
                decision = _routing_decision(message)
                self.assertEqual(decision["route"], expected_route, msg=decision)


if __name__ == "__main__":
    unittest.main()
