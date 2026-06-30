"""Tests for comparison-safety policy in the Analysis Assistant."""

import os
import unittest
from unittest.mock import patch

from app.services.comparison_labels import (
    COMPARISON_PERIOD_CLARIFICATION,
    COMPARISON_TWO_PERIODS_CLARIFICATION,
    comparison_needs_period_clarification,
    message_has_explicit_comparison_pair,
    revenue_drivers_comparison_label,
    rolling_change_comparison_label,
)
from app.services.intent_router import (
    PriorTurnContext,
    plan_comparison_followup_tools,
    plan_forced_tools,
)
from app.services.period_labels import enrich_declining_products_metadata
from app.services.tool_planner import resolve_tool_plans


SUPPLIER = "Coca-Cola Europacific Partners Sverige"


def _prior_30_day_trend() -> PriorTurnContext:
    start, end = "2026-05-24", "2026-06-22"
    return PriorTurnContext(
        question="Hur ser försäljningen ut senaste 30 dagarna?",
        tool_calls=("get_sales_over_time",),
        sources=({"tool": "get_sales_over_time", "date_range": {"start": start, "end": end}},),
        has_chart=True,
        analysis_context={
            "prior_intent": "sales_trend",
            "start_date": start,
            "end_date": end,
            "period_kind": "rolling_30",
            "prior_tool_calls": ["get_sales_over_time"],
        },
    )


def _prior_ytd_overview() -> PriorTurnContext:
    start, end = "2026-01-01", "2026-06-22"
    return PriorTurnContext(
        question="Hur har försäljningen gått i år?",
        tool_calls=("get_supplier_kpis", "get_sales_over_time"),
        sources=(
            {"tool": "get_supplier_kpis", "date_range": {"start": start, "end": end}},
            {"tool": "get_sales_over_time", "date_range": {"start": start, "end": end}},
        ),
        has_chart=True,
        analysis_context={
            "prior_intent": "sales_overview",
            "start_date": start,
            "end_date": end,
            "period_kind": "year_to_date",
            "prior_tool_calls": ["get_supplier_kpis", "get_sales_over_time"],
        },
    )


class ComparisonSafetyPolicyTests(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"USE_AI_PLANNER": "false"})
        self._env_patch.start()

    def tearDown(self):
        self._env_patch.stop()

    def test_1_new_chat_ambiguous_comparison_clarifies(self):
        for message in (
            "Jämför försäljningen med förra perioden",
            "Jämför med tidigare",
            "Hur skiljer det sig från förut?",
            "Har försäljningen ökat eller minskat?",
        ):
            with self.subTest(message=message):
                self.assertTrue(comparison_needs_period_clarification(message))
                self.assertEqual(plan_forced_tools(message, SUPPLIER), [])
                resolution = resolve_tool_plans(message, SUPPLIER)
                self.assertEqual(resolution.clarification_answer, COMPARISON_TWO_PERIODS_CLARIFICATION)
                self.assertEqual(resolution.plans, [])

    def test_2_explicit_rolling_30_vs_30_comparison(self):
        message = "Jämför senaste 30 dagarna mot föregående 30 dagar"
        self.assertTrue(message_has_explicit_comparison_pair(message))
        self.assertFalse(comparison_needs_period_clarification(message))
        plans = plan_forced_tools(message, SUPPLIER)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_revenue_drivers")
        self.assertEqual(plans[0].args.get("_chart_intent"), "period_comparison")
        self.assertEqual(plans[0].args.get("days"), 30)

    def test_3_explicit_ytd_vs_prior_year(self):
        message = "Jämför i år jämfört med förra året"
        self.assertTrue(message_has_explicit_comparison_pair(message))
        self.assertFalse(comparison_needs_period_clarification(message))
        plans = plan_forced_tools(message, SUPPLIER)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_supplier_kpis")
        self.assertEqual(plans[0].args.get("_chart_intent"), "period_comparison")

    def test_4_followup_after_trend_reuses_prior_period(self):
        prior = _prior_30_day_trend()
        message = "Jämför med föregående period"
        self.assertFalse(comparison_needs_period_clarification(message, prior))
        plans = plan_comparison_followup_tools(message, prior, SUPPLIER)
        self.assertEqual(plans[0].tool_name, "get_revenue_drivers")
        self.assertEqual(plans[0].args.get("days"), 30)
        resolution = resolve_tool_plans(message, SUPPLIER, prior_context=prior)
        self.assertIsNone(resolution.clarification_answer)
        self.assertEqual(resolution.plans[0].tool_name, "get_revenue_drivers")

    def test_5_trend_without_automatic_comparison(self):
        message = "Hur ser försäljningen ut senaste 30 dagarna?"
        self.assertFalse(comparison_needs_period_clarification(message))
        plans = plan_forced_tools(message, SUPPLIER)
        tool_names = [p.tool_name for p in plans]
        self.assertIn("get_sales_over_time", tool_names)
        self.assertNotIn("get_revenue_drivers", tool_names)
        for plan in plans:
            self.assertNotEqual(plan.args.get("_chart_intent"), "period_comparison")

    def test_6_decline_rolling_shows_both_periods(self):
        message = "Vilken produkt har tappat mest senaste 30 dagarna?"
        self.assertFalse(comparison_needs_period_clarification(message))
        plans = plan_forced_tools(message, SUPPLIER)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_declining_products")
        self.assertEqual(plans[0].args.get("days"), 30)

        payload = enrich_declining_products_metadata({
            "comparison_days": 30,
            "prior_period": {"start": "2026-04-24", "end": "2026-05-23"},
            "latest_period": {"start": "2026-05-24", "end": "2026-06-22"},
            "products": [{"product_name": "Test", "revenue_change": -100.0}],
        })
        label = payload["comparison_period_label"]
        self.assertIn("Senaste 30 dagarna", label)
        self.assertIn("jämfört med", label)
        self.assertIn("föregående 30 dagar", label)
        self.assertIn("24 april", label)
        self.assertIn("22 juni", label)

    def test_rolling_change_label_shows_both_windows(self):
        label = rolling_change_comparison_label({
            "comparison_days": 30,
            "current_period": {"start": "2026-05-24", "end": "2026-06-22"},
            "prior_period": {"start": "2026-04-24", "end": "2026-05-23"},
        })
        self.assertIn("Senaste 30 dagarna", label)
        self.assertIn("24 maj", label)
        self.assertIn("22 juni", label)
        self.assertIn("föregående 30 dagar", label)
        self.assertIn("24 april", label)
        self.assertEqual(label, revenue_drivers_comparison_label({
            "comparison_days": 30,
            "current_period": {"start": "2026-05-24", "end": "2026-06-22"},
            "prior_period": {"start": "2026-04-24", "end": "2026-05-23"},
        }))

    def test_followup_after_ytd(self):
        prior = _prior_ytd_overview()
        message = "Jämför med föregående period"
        plans = plan_comparison_followup_tools(message, prior, SUPPLIER)
        self.assertEqual(plans[0].tool_name, "get_supplier_kpis")
        self.assertEqual(plans[0].args.get("_period_kind"), "year_to_date")


if __name__ == "__main__":
    unittest.main()
