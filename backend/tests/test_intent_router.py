"""
Unit tests for deterministic intent routing (no API / LLM required).
Run: python -m unittest tests.test_intent_router
"""

import unittest
from datetime import date, timedelta

from app.services.chart_policy import select_charts
from app.services.chart_builder import LINE_CHART, BAR_CHART
from app.services.intent_router import (
    PriorTurnContext,
    default_category_for_supplier,
    extract_category,
    extract_period_args,
    extract_region,
    is_diagram_followup_request,
    is_long_term_trend_request,
    is_period_only_followup,
    plan_followup_tools,
    plan_forced_tools,
    plan_long_term_trend_tools,
    plan_period_followup_tools,
)
from app.services.period_utils import completed_week_bounds, latest_completed_date


class IntentRouterTests(unittest.TestCase):
    UI_START = "2026-03-25"
    UI_END = "2026-06-23"

    def _expected_ytd(self) -> tuple[str, str]:
        return f"{date.today().year}-01-01", latest_completed_date().isoformat()

    def test_ytd_overview_overrides_ui_default(self):
        plans = plan_forced_tools(
            "Hur ser försäljningen överlag ut detta år?",
            "Orkla Snacks Sverige",
            start_date=self.UI_START,
            end_date=self.UI_END,
        )
        ytd_start, ytd_end = self._expected_ytd()
        self.assertEqual(len(plans), 2)
        self.assertEqual(plans[0].tool_name, "get_supplier_kpis")
        self.assertEqual(plans[1].tool_name, "get_sales_over_time")
        self.assertEqual(plans[0].args["start_date"], ytd_start)
        self.assertEqual(plans[0].args["end_date"], ytd_end)
        self.assertEqual(plans[1].args["granularity"], "month")
        self.assertEqual(plans[1].args.get("_chart_intent"), "time_series")

    def test_ytd_sales_overview_monthly_trend(self):
        plans = plan_forced_tools(
            "Hur ser försäljningen ut i år?",
            "Orkla Snacks Sverige",
            start_date=self.UI_START,
            end_date=self.UI_END,
        )
        ytd_start, ytd_end = self._expected_ytd()
        self.assertEqual(len(plans), 2)
        self.assertEqual(plans[1].args["start_date"], ytd_start)
        self.assertEqual(plans[1].args["end_date"], ytd_end)
        self.assertEqual(plans[1].args["granularity"], "month")

    def test_ytd_development_monthly_time_series(self):
        plans = plan_forced_tools(
            "Hur har försäljningen utvecklats i år?",
            "Orkla Snacks Sverige",
            start_date=self.UI_START,
            end_date=self.UI_END,
        )
        ytd_start, ytd_end = self._expected_ytd()
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_sales_over_time")
        self.assertEqual(plans[0].args["start_date"], ytd_start)
        self.assertEqual(plans[0].args["end_date"], ytd_end)
        self.assertEqual(plans[0].args["granularity"], "month")
        self.assertEqual(plans[0].args.get("_chart_intent"), "time_series")
        charts = select_charts(
            "Hur har försäljningen utvecklats i år?",
            [("get_sales_over_time", {
                **plans[0].args,
                "granularity": "month",
                "series": [
                    {"period": "2026-01-01", "revenue": 1.0},
                    {"period": "2026-02-01", "revenue": 2.0},
                    {"period": "2026-03-01", "revenue": 3.0},
                ],
            })],
        )
        self.assertEqual(charts[0]["chart_type"], LINE_CHART)

    def test_ytd_weekly_drill_preserves_ytd_dates(self):
        plans = plan_forced_tools(
            "Visa utveckling per vecka i år",
            "Orkla Snacks Sverige",
            start_date=self.UI_START,
            end_date=self.UI_END,
        )
        ytd_start, ytd_end = self._expected_ytd()
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_sales_over_time")
        self.assertEqual(plans[0].args["granularity"], "week")
        self.assertEqual(plans[0].args["start_date"], ytd_start)
        self.assertEqual(plans[0].args["end_date"], ytd_end)
        self.assertTrue(plans[0].args.get("_force_time_series"))

    def test_ytd_top_products_ranking(self):
        plans = plan_forced_tools(
            "Vilka produkter säljer bäst i år?",
            "Orkla Snacks Sverige",
            start_date=self.UI_START,
            end_date=self.UI_END,
        )
        ytd_start, ytd_end = self._expected_ytd()
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_top_products")
        self.assertEqual(plans[0].args["start_date"], ytd_start)
        self.assertEqual(plans[0].args["end_date"], ytd_end)
        charts = select_charts(
            "Vilka produkter säljer bäst i år?",
            [("get_top_products", {
                "products": [
                    {"product_name": "A", "revenue": 10.0},
                    {"product_name": "B", "revenue": 5.0},
                ],
            })],
        )
        self.assertEqual(charts[0]["chart_type"], BAR_CHART)
        self.assertEqual(charts[0].get("layout"), "horizontal")

    def test_default_category_cocacola(self):
        self.assertEqual(default_category_for_supplier("Coca-Cola Europacific Partners Sverige"), "Läsk")

    def test_default_category_orkla_snacks(self):
        self.assertEqual(default_category_for_supplier("Orkla Snacks Sverige"), "Chips & snacks")

    def test_brand_vs_competitors_forces_market_share_lask(self):
        plans = plan_forced_tools(
            "Hur går det för vårt märke jämfört med konkurrenterna?",
            "Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_market_share")
        self.assertEqual(plans[0].args["category_name"], "Läsk")

    def test_explicit_lask_market_share(self):
        plans = plan_forced_tools(
            "Vad är vår marknadsandel i Läsk?",
            "Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_market_share")
        self.assertEqual(plans[0].args["category_name"], "Läsk")

    def test_top_products_stockholm(self):
        plans = plan_forced_tools(
            "Vilka produkter säljer bäst i Stockholm?",
            "Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_top_products")
        self.assertEqual(plans[0].args["region"], "Stockholm")

    def test_all_products_this_year_overrides_ui_default_window(self):
        plans = plan_forced_tools(
            "Jämför försäljningen för alla produkter vi har över detta år",
            "Orkla Snacks Sverige",
            start_date="2026-03-25",
            end_date="2026-06-23",
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_top_products")
        self.assertEqual(plans[0].args.get("limit"), 50)
        self.assertEqual(plans[0].args["start_date"], f"{date.today().year}-01-01")
        self.assertEqual(plans[0].args["end_date"], (date.today() - timedelta(days=1)).isoformat())
        self.assertNotIn("region", plans[0].args)

    def test_sales_trend_90_days(self):
        plans = plan_forced_tools(
            "Hur har försäljningen utvecklats de senaste 90 dagarna?",
            "Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_sales_over_time")

    def test_sales_trend_last_week(self):
        # Weekly direct question: 2-week window (prev + current completed week),
        # chart suppressed (LLM gets comparison data, chart shown separately on request).
        plans = plan_forced_tools(
            "Hur såg försäljningen ut senaste veckan?",
            "Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_sales_over_time")
        self.assertEqual(plans[0].args.get("granularity"), "week")
        self.assertTrue(plans[0].args.get("_suppress_chart"))
        week_start, week_end = completed_week_bounds()
        prev_start = week_start - timedelta(days=7)
        self.assertEqual(plans[0].args.get("start_date"), prev_start.isoformat())
        self.assertEqual(plans[0].args.get("end_date"), week_end.isoformat())

    def test_sales_trend_30_days_deep_dive(self):
        plans = plan_forced_tools(
            "Hur har försäljningen utvecklats de senaste 30 dagarna?",
            "Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(len(plans), 2)
        self.assertEqual(plans[0].tool_name, "get_revenue_drivers")
        self.assertEqual(plans[1].tool_name, "get_sales_over_time")
        self.assertEqual(plans[1].args.get("_chart_intent"), "time_series")
        self.assertTrue(plans[1].args.get("_force_time_series"))

    def test_period_comparison_routes_to_revenue_drivers(self):
        plans = plan_forced_tools(
            "Jämför senaste 30 dagarna med föregående 30 dagar",
            "Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_revenue_drivers")
        self.assertEqual(plans[0].args.get("_chart_intent"), "period_comparison")

    def test_sales_trend_30_days_weekly_granularity(self):
        plans = plan_forced_tools(
            "Hur har försäljningen utvecklats senaste 30 dagarna?",
            "Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(plans[0].tool_name, "get_revenue_drivers")
        self.assertEqual(plans[1].args.get("granularity"), "week")

    def test_product_decline_30_days(self):
        plans = plan_forced_tools(
            "Vilken produkt har tappat mest de senaste 30 dagarna?",
            "Orkla Snacks Sverige",
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_declining_products")
        self.assertEqual(plans[0].args.get("days"), 30)

    def test_period_followup_sales_trend(self):
        prior = PriorTurnContext(
            question="Hur såg försäljningen ut senaste veckan?",
            tool_calls=("get_sales_over_time",),
            sources=({"date_range": {"start": "2026-06-16", "end": "2026-06-22"}},),
        )
        self.assertTrue(is_period_only_followup("senaste 30 dagarna då?"))
        plans = plan_period_followup_tools(
            "senaste 30 dagarna då?",
            prior,
            "Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_sales_over_time")
        self.assertIn("start_date", plans[0].args)
        self.assertIn("end_date", plans[0].args)
        self.assertEqual(plans[0].args.get("granularity"), "week")

    def test_period_followup_market_share(self):
        prior = PriorTurnContext(
            question="Vad är vår marknadsandel i Läsk?",
            tool_calls=("get_market_share",),
        )
        plans = plan_forced_tools(
            "senaste 30 dagarna då?",
            "Coca-Cola Europacific Partners Sverige",
            prior_context=prior,
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_market_share")
        self.assertEqual(plans[0].args["category_name"], "Läsk")

    def test_period_followup_top_products_stockholm(self):
        prior = PriorTurnContext(
            question="Vilka produkter säljer bäst i Stockholm?",
            tool_calls=("get_top_products",),
        )
        plans = plan_forced_tools(
            "senaste 30 dagarna då?",
            "Coca-Cola Europacific Partners Sverige",
            prior_context=prior,
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_top_products")
        self.assertEqual(plans[0].args["region"], "Stockholm")

    def test_period_followup_not_subject_change(self):
        prior = PriorTurnContext(
            question="Hur såg försäljningen ut senaste veckan?",
            tool_calls=("get_sales_over_time",),
        )
        plans = plan_forced_tools(
            "Vad är vår marknadsandel i Läsk?",
            "Coca-Cola Europacific Partners Sverige",
            prior_context=prior,
        )
        self.assertEqual(plans[0].tool_name, "get_market_share")

    def test_focus_question_forces_declining(self):
        plans = plan_forced_tools(
            "Vad borde vi fokusera på nästa period?",
            "Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_declining_products")

    def test_diagram_followup_market_share(self):
        prior = PriorTurnContext(
            question="Vad är vår marknadsandel i Läsk?",
            tool_calls=("get_market_share",),
            sources=({"date_range": {"start": "2026-03-25", "end": "2026-06-23"}},),
        )
        plans = plan_followup_tools(
            "Visa ett diagram för det.",
            prior,
            "Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_market_share")
        self.assertEqual(plans[0].args["category_name"], "Läsk")

    def test_diagram_followup_top_products_stockholm(self):
        prior = PriorTurnContext(
            question="Vilka produkter säljer bäst i Stockholm?",
            tool_calls=("get_top_products",),
        )
        plans = plan_followup_tools(
            "Visa ett diagram för det",
            prior,
            "Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(plans[0].tool_name, "get_top_products")
        self.assertEqual(plans[0].args["region"], "Stockholm")

    def test_diagram_followup_declining_products(self):
        prior = PriorTurnContext(
            question="Vilken produkt minskade mest de senaste 30 dagarna?",
            tool_calls=("get_declining_products",),
        )
        plans = plan_followup_tools(
            "Visa diagram för det",
            prior,
            "Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(plans[0].tool_name, "get_declining_products")

    def test_diagram_followup_kpi_maps_to_sales_trend(self):
        prior = PriorTurnContext(
            question="Hur ser försäljningen ut jämfört med föregående period?",
            tool_calls=("get_supplier_kpis",),
        )
        plans = plan_followup_tools(
            "Visa ett diagram för det.",
            prior,
            "Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(plans[0].tool_name, "get_sales_over_time")

    def test_weekly_end_date_is_latest_completed_sunday(self):
        _, week_end = completed_week_bounds()
        plans = plan_forced_tools(
            "Hur såg försäljningen ut senaste veckan?",
            "Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(plans[0].args.get("end_date"), week_end.isoformat())
        wrong_end = (week_end - timedelta(days=7)).isoformat()
        self.assertNotEqual(plans[0].args.get("end_date"), wrong_end)

    def test_sales_trend_last_week_suppresses_chart(self):
        # Direct weekly question must NOT auto-widen to 8 weeks.
        plans = plan_forced_tools(
            "Hur såg försäljningen ut senaste veckan?",
            "Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(len(plans), 1)
        self.assertTrue(plans[0].args.get("_suppress_chart"))
        self.assertFalse(plans[0].args.get("_chart_context_widened"))

    def test_regional_sales_routing(self):
        plans = plan_forced_tools(
            "Vilken region genererar mest intäkter?",
            "Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_sales_by_region")

    def test_redundant_diagram_followup_skipped_when_chart_shown(self):
        prior = PriorTurnContext(
            question="Vad är vår marknadsandel i Läsk?",
            tool_calls=("get_market_share",),
            has_chart=True,
        )
        plans = plan_followup_tools("visa diagram", prior, "Coca-Cola Europacific Partners Sverige")
        self.assertEqual(plans, [])

    def test_diagram_followup_visa_diagram_after_weekly_sales_is_daily_exact_week(self):
        # "visa diagram" after weekly answer must show a 7-day daily chart for the
        # EXACT completed week discussed — not widened to 8 weeks.
        week_start, week_end = completed_week_bounds()
        prev_start = week_start - timedelta(days=7)
        prior = PriorTurnContext(
            question="Hur såg försäljningen ut senaste veckan?",
            tool_calls=("get_sales_over_time",),
            # sources end date is Sunday of the answered week (always a real Sunday)
            sources=({"date_range": {"start": prev_start.isoformat(), "end": week_end.isoformat()}},),
        )
        plans = plan_followup_tools("visa diagram", prior, "Coca-Cola Europacific Partners Sverige")
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_sales_over_time")
        # Must be daily granularity for the within-week breakdown
        self.assertEqual(plans[0].args.get("granularity"), "day")
        start = plans[0].args.get("start_date")
        end = plans[0].args.get("end_date")
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
        # Exactly 7 days (Mon–Sun)
        span = (date.fromisoformat(end[:10]) - date.fromisoformat(start[:10])).days + 1
        self.assertEqual(span, 7)
        # End must match the Sunday in prior sources; start is 6 days earlier (Mon)
        self.assertEqual(end[:10], week_end.isoformat())
        self.assertEqual(start[:10], week_start.isoformat())

    def test_long_term_trend_after_weekly_sales_is_8_weeks(self):
        # Explicitly asking for trend must widen to 8 weeks.
        week_start, week_end = completed_week_bounds()
        prev_start = week_start - timedelta(days=7)
        prior = PriorTurnContext(
            question="Hur såg försäljningen ut senaste veckan?",
            tool_calls=("get_sales_over_time",),
            sources=({"date_range": {"start": prev_start.isoformat(), "end": week_end.isoformat()}},),
        )
        plans = plan_long_term_trend_tools("Visa trenden", prior, "Coca-Cola Europacific Partners Sverige")
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_sales_over_time")
        self.assertEqual(plans[0].args.get("granularity"), "week")
        start = plans[0].args.get("start_date")
        end = plans[0].args.get("end_date")
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
        span = (date.fromisoformat(end[:10]) - date.fromisoformat(start[:10])).days + 1
        self.assertGreaterEqual(span, 49)  # at least 7 completed weeks
        self.assertTrue(plans[0].args.get("_chart_context_widened"))

    def test_long_term_via_forced_tools(self):
        # plan_forced_tools must dispatch to plan_long_term_trend_tools when prior context exists.
        week_start, week_end = completed_week_bounds()
        prev_start = week_start - timedelta(days=7)
        prior = PriorTurnContext(
            question="Hur såg försäljningen ut senaste veckan?",
            tool_calls=("get_sales_over_time",),
            sources=({"date_range": {"start": prev_start.isoformat(), "end": week_end.isoformat()}},),
        )
        for phrase in ("Visa trenden", "Visa utvecklingen över tid", "visa trend"):
            with self.subTest(phrase=phrase):
                plans = plan_forced_tools(phrase, "Coca-Cola Europacific Partners Sverige", prior_context=prior)
                self.assertEqual(len(plans), 1, msg=f"No plan for '{phrase}'")
                self.assertEqual(plans[0].tool_name, "get_sales_over_time")
                self.assertTrue(plans[0].args.get("_chart_context_widened"))

    def test_is_long_term_trend_request(self):
        self.assertTrue(is_long_term_trend_request("Visa trenden"))
        self.assertTrue(is_long_term_trend_request("Visa trend"))
        self.assertTrue(is_long_term_trend_request("Visa utvecklingen över tid"))
        self.assertTrue(is_long_term_trend_request("jämför med tidigare veckor"))
        self.assertFalse(is_long_term_trend_request("visa diagram"))
        self.assertFalse(is_long_term_trend_request("Vad är vår marknadsandel?"))

    def test_30_day_trend_returns_weekly_chart_directly(self):
        # 30-day trend should not suppress the chart.
        plans = plan_forced_tools(
            "Visa försäljningstrend de senaste 30 dagarna",
            "Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_sales_over_time")
        self.assertFalse(plans[0].args.get("_suppress_chart"))

    def test_visa_diagram_does_not_change_period_for_non_weekly(self):
        # "visa diagram" after a 30-day trend with chart already shown → skipped.
        prior = PriorTurnContext(
            question="Visa försäljningstrend de senaste 30 dagarna",
            tool_calls=("get_sales_over_time",),
            has_chart=True,
        )
        plans = plan_followup_tools("visa diagram", prior, "Coca-Cola Europacific Partners Sverige")
        self.assertEqual(plans, [], msg="Should not re-plan when chart already shown")

    def test_is_diagram_followup(self):
        self.assertTrue(is_diagram_followup_request("Visa ett diagram för det."))
        self.assertTrue(is_diagram_followup_request("visa diagram"))
        self.assertTrue(is_diagram_followup_request("visa graf"))
        self.assertTrue(is_diagram_followup_request("kan du visa det i graf?"))
        self.assertTrue(is_diagram_followup_request("visa ett diagram"))
        self.assertFalse(is_diagram_followup_request("Vad är vår marknadsandel?"))

    def test_extract_category_and_region(self):
        self.assertEqual(extract_category("Marknadsandel i Läsk"), "Läsk")
        self.assertEqual(extract_region("försäljning i Göteborg"), "Göteborg")


if __name__ == "__main__":
    unittest.main()
