"""Tests for declining-product period clarification and visualization."""

import unittest

from app.services.chart_builder import build_decline_ranking_chart, build_decline_trend_chart
from app.services.chart_policy import select_charts
from app.services.decline_period import (
    DECLINE_PERIOD_CLARIFICATION,
    decline_question_needs_period,
    plan_awaiting_decline_period,
)
from app.services.intent_router import plan_forced_tools
from app.services.plan_normalizer import normalize_plan
from app.services.tool_planner import resolve_tool_plans
from app.schemas.analysis_plan import AnalysisPlan, TimePeriod


class DeclinePeriodTests(unittest.TestCase):
    def test_ambiguous_decline_question_needs_period(self):
        self.assertTrue(decline_question_needs_period("Vilken produkt har tappat mest?"))
        self.assertFalse(decline_question_needs_period("Vilken produkt har tappat mest de senaste 30 dagarna?"))

    def test_plan_normalizer_returns_clarification_without_period(self):
        norm = normalize_plan(
            AnalysisPlan(intent="product_decline", time_period=TimePeriod(kind="unspecified"), confidence=0.9),
            "Vilken produkt har tappat mest?",
            "Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(norm.clarification_answer, DECLINE_PERIOD_CLARIFICATION)
        self.assertEqual(norm.tool_plans, [])

    def test_resolve_tool_plans_clarification_without_period(self):
        resolution = resolve_tool_plans(
            "Vilken produkt har tappat mest?",
            "Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(resolution.clarification_answer, DECLINE_PERIOD_CLARIFICATION)
        self.assertEqual(resolution.plans, [])

    def test_legacy_forced_tools_skip_ambiguous_decline(self):
        plans = plan_forced_tools("Vilken produkt har tappat mest?", "Coca-Cola Sverige")
        self.assertEqual(plans, [])

    def test_period_followup_after_clarification(self):
        plans = plan_awaiting_decline_period("senaste 30 dagarna")
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_declining_products")
        self.assertEqual(plans[0].args.get("days"), 30)
        self.assertEqual(plans[0].args.get("_period_kind"), "rolling_30")

    def test_explicit_30_day_decline_plan(self):
        norm = normalize_plan(
            AnalysisPlan(intent="product_decline", time_period=TimePeriod(kind="unspecified"), confidence=0.9),
            "Vilken produkt har tappat mest de senaste 30 dagarna?",
            "Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(len(norm.tool_plans), 1)
        self.assertEqual(norm.tool_plans[0].args.get("days"), 30)


def _decline_payload() -> dict:
    return {
        "comparison_days": 30,
        "latest_period": {"start": "2026-05-24", "end": "2026-06-23"},
        "prior_period": {"start": "2026-04-24", "end": "2026-05-23"},
        "_period_kind": "rolling_30",
        "products": [
            {
                "product_name": "Coca-Cola Zero Sugar Lemon 33 cl",
                "revenue_change_pct": -35.9,
                "revenue_change": -80700.0,
                "latest_period_revenue": 144300.0,
                "prior_period_revenue": 225000.0,
            },
            {
                "product_name": "Coca-Cola Original 33 cl",
                "revenue_change_pct": -2.5,
                "revenue_change": -51600.0,
                "latest_period_revenue": 2000000.0,
                "prior_period_revenue": 2051600.0,
            },
        ],
        "focus_product_weekly_series": [
            {"period": "2026-04-28", "revenue": 50000.0},
            {"period": "2026-05-05", "revenue": 52000.0},
            {"period": "2026-05-12", "revenue": 48000.0},
            {"period": "2026-05-19", "revenue": 45000.0},
            {"period": "2026-05-26", "revenue": 38000.0},
            {"period": "2026-06-02", "revenue": 36000.0},
            {"period": "2026-06-09", "revenue": 34000.0},
        ],
        "focus_product_regions": [
            {"region": "Stockholm", "revenue_change": -40000.0, "revenue_change_pct": -30.0},
        ],
    }


class DeclineVisualizationTests(unittest.TestCase):
    def test_trend_chart_primary_for_decline(self):
        payload = _decline_payload()
        trend = build_decline_trend_chart(payload)
        self.assertIsNotNone(trend)
        assert trend is not None
        self.assertEqual(trend["chart_type"], "line_chart")
        self.assertEqual(trend["chart_variant"], "decline_trend")
        self.assertIn("Coca-Cola Zero Sugar Lemon", trend["title"])
        self.assertIn("decline_metrics", trend)
        self.assertEqual(trend["decline_metrics"]["revenue_change"], -80700.0)

    def test_ranking_sorted_by_sek_not_pct(self):
        payload = _decline_payload()
        ranking = build_decline_ranking_chart(payload)
        self.assertIsNotNone(ranking)
        assert ranking is not None
        self.assertEqual(ranking["chart_variant"], "decline_ranking")
        self.assertEqual(ranking["y_key"], "revenue_change")
        self.assertEqual(ranking["data"][0]["product_name"], "Coca-Cola Zero Sugar Lemon 33 cl")
        self.assertEqual(ranking["data"][1]["product_name"], "Coca-Cola Original 33 cl")

    def test_pct_decline_does_not_win_ranking(self):
        payload = _decline_payload()
        payload["products"] = [
            {
                "product_name": "Small pct big sek",
                "revenue_change_pct": -5.0,
                "revenue_change": -100000.0,
                "latest_period_revenue": 1900000.0,
                "prior_period_revenue": 2000000.0,
            },
            {
                "product_name": "Big pct small sek",
                "revenue_change_pct": -50.0,
                "revenue_change": -10000.0,
                "latest_period_revenue": 10000.0,
                "prior_period_revenue": 20000.0,
            },
        ]
        ranking = build_decline_ranking_chart(payload)
        assert ranking is not None
        self.assertEqual(ranking["data"][0]["product_name"], "Small pct big sek")

    def test_chart_policy_primary_trend_secondary_ranking(self):
        q = "Vilken produkt har tappat mest de senaste 30 dagarna?"
        charts = select_charts(q, [("get_declining_products", _decline_payload())])
        self.assertGreaterEqual(len(charts), 2)
        self.assertEqual(charts[0]["chart_variant"], "decline_trend")
        self.assertEqual(charts[0]["chart_role"], "primary")
        self.assertEqual(charts[1]["chart_variant"], "decline_ranking")
        self.assertEqual(charts[1]["chart_role"], "secondary")
        self.assertIn("Coca-Cola Zero Sugar Lemon", charts[0]["title"])

    def test_trend_chart_has_period_split(self):
        trend = build_decline_trend_chart(_decline_payload())
        assert trend is not None
        self.assertEqual(trend.get("period_split_at"), "2026-05-24")
        phases = {row.get("period_phase") for row in trend["data"]}
        self.assertIn("prior", phases)
        self.assertIn("latest", phases)


class DeclinePeriodContextFlowTests(unittest.TestCase):
    """Simulate the actual frontend→backend request/context flow for decline clarification."""

    def _make_prior_context_with_awaiting(self) -> dict:
        """The prior_context dict the frontend sends after the clarification response."""
        return {
            "question": "Vilken produkt har tappat mest?",
            "answer": DECLINE_PERIOD_CLARIFICATION,
            "tool_calls": [],
            "sources": [],
            "has_chart": False,
            "analysis_context": {
                "awaiting_decline_period": True,
                "prior_intent": "product_decline",
            },
        }

    def _resolve(self, message: str, prior_context: dict | None = None) -> "ToolResolution":
        from app.services.intent_router import prior_context_from_dict
        prior = prior_context_from_dict(prior_context) if prior_context else None
        return resolve_tool_plans(
            message,
            "Coca-Cola Europacific Partners Sverige",
            prior_context=prior,
        )

    # --- Step 1: Clarification is requested for ambiguous decline question ---
    def test_step1_ambiguous_decline_returns_clarification(self):
        resolution = self._resolve("Vilken produkt har tappat mest?")
        self.assertIsNotNone(resolution.clarification_answer)
        self.assertEqual(resolution.plans, [])

    # --- Step 2: "senaste 30 dagarna" with awaiting context → product_decline ---
    def test_step2_period_reply_resolves_to_decline(self):
        prior = self._make_prior_context_with_awaiting()
        resolution = self._resolve("senaste 30 dagarna", prior)
        self.assertEqual(len(resolution.plans), 1)
        self.assertEqual(resolution.plans[0].tool_name, "get_declining_products")
        self.assertEqual(resolution.plans[0].args.get("days"), 30)

    # --- Step 3: "i år" with awaiting context → product_decline for current year ---
    def test_step3_current_year_reply_resolves_to_decline(self):
        prior = self._make_prior_context_with_awaiting()
        resolution = self._resolve("i år", prior)
        self.assertEqual(len(resolution.plans), 1)
        self.assertEqual(resolution.plans[0].tool_name, "get_declining_products")

    # --- Step 3b: "senaste 12 månaderna" with awaiting context ---
    def test_step3b_12months_reply_resolves_to_decline(self):
        prior = self._make_prior_context_with_awaiting()
        resolution = self._resolve("senaste 12 månaderna", prior)
        self.assertEqual(len(resolution.plans), 1)
        self.assertEqual(resolution.plans[0].tool_name, "get_declining_products")
        self.assertGreaterEqual(resolution.plans[0].args.get("days", 0), 360)

    # --- Step 4: No awaiting context → "senaste 30 dagarna" does NOT trigger decline ---
    def test_step4_no_prior_context_period_is_not_decline(self):
        resolution = self._resolve("senaste 30 dagarna")
        # Must NOT be a product_decline — will be a sales trend or overview
        tools = [p.tool_name for p in resolution.plans]
        self.assertNotIn("get_declining_products", tools)

    # --- Step 5: Full sentence decline question with period stays normal ---
    def test_step5_full_sentence_with_period_is_not_decline_clarification(self):
        resolution = self._resolve("Hur har försäljningen utvecklats de senaste 30 dagarna?")
        # Should return normal sales development, no clarification
        self.assertIsNone(resolution.clarification_answer)
        tools = [p.tool_name for p in resolution.plans]
        self.assertNotIn("get_declining_products", tools)

    # --- Ensure "30 dagar" and bare variants also work ---
    def test_bare_days_reply_resolves_to_decline(self):
        prior = self._make_prior_context_with_awaiting()
        for phrase in ["30 dagar", "förra året", "senaste 12 månaderna", "12 månader"]:
            with self.subTest(phrase=phrase):
                resolution = self._resolve(phrase, prior)
                self.assertEqual(len(resolution.plans), 1, msg=f"Failed for: {phrase!r}")
                self.assertEqual(resolution.plans[0].tool_name, "get_declining_products", msg=f"Failed for: {phrase!r}")


if __name__ == "__main__":
    unittest.main()
