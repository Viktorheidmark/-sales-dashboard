"""Tests for deterministic plan normalization."""

import unittest
from datetime import date, timedelta

from app.schemas.analysis_plan import AnalysisPlan, AnalysisFilters, TimePeriod, VisualizationSpec
from app.services.intent_router import PriorTurnContext
from app.services.period_utils import latest_completed_date
from app.services.plan_normalizer import normalize_plan, ALLOWED_TOOLS


class PlanNormalizerTests(unittest.TestCase):
    UI_START = "2026-03-25"
    UI_END = "2026-06-23"
    SUPPLIER = "Orkla Snacks Sverige"

    def _ytd_plan(self, intent: str, **kwargs) -> AnalysisPlan:
        return AnalysisPlan(
            intent=intent,  # type: ignore[arg-type]
            time_period=TimePeriod(kind="year_to_date"),
            confidence=0.9,
            visualization=VisualizationSpec(primary="line", granularity="month"),
            **kwargs,
        )

    def _expected_ytd(self) -> tuple[str, str]:
        return f"{date.today().year}-01-01", latest_completed_date().isoformat()

    def test_ytd_sales_overview(self):
        norm = normalize_plan(
            self._ytd_plan("sales_overview"),
            "Hur ser försäljningen ut i år?",
            self.SUPPLIER,
            ui_start=self.UI_START,
            ui_end=self.UI_END,
        )
        ytd_start, ytd_end = self._expected_ytd()
        self.assertFalse(norm.use_fallback)
        assert norm.meta
        self.assertEqual(norm.meta.resolved_start_date, ytd_start)
        self.assertEqual(norm.meta.resolved_end_date, ytd_end)
        self.assertEqual(norm.meta.intent, "sales_overview")
        tools = [p.tool_name for p in norm.tool_plans]
        self.assertIn("get_supplier_kpis", tools)
        self.assertIn("get_sales_over_time", tools)

    def test_ytd_overlag_identical_period(self):
        a = normalize_plan(
            self._ytd_plan("sales_overview"),
            "Hur ser försäljningen överlag ut detta år?",
            self.SUPPLIER,
            ui_start=self.UI_START,
            ui_end=self.UI_END,
        )
        b = normalize_plan(
            self._ytd_plan("sales_overview"),
            "Hur ser försäljningen ut i år?",
            self.SUPPLIER,
            ui_start=self.UI_START,
            ui_end=self.UI_END,
        )
        assert a.meta and b.meta
        self.assertEqual(a.meta.resolved_start_date, b.meta.resolved_start_date)
        self.assertEqual(a.meta.resolved_end_date, b.meta.resolved_end_date)

    def test_ytd_development_monthly_trend(self):
        norm = normalize_plan(
            self._ytd_plan("sales_trend"),
            "Hur har försäljningen utvecklats i år?",
            self.SUPPLIER,
            ui_start=self.UI_START,
            ui_end=self.UI_END,
        )
        self.assertFalse(norm.use_fallback)
        self.assertEqual(len(norm.tool_plans), 1)
        self.assertEqual(norm.tool_plans[0].tool_name, "get_sales_over_time")
        self.assertEqual(norm.tool_plans[0].args["granularity"], "month")
        self.assertEqual(norm.tool_plans[0].args.get("_chart_intent"), "time_series")

    def test_ytd_product_ranking(self):
        norm = normalize_plan(
            AnalysisPlan(
                intent="product_ranking",
                time_period=TimePeriod(kind="year_to_date"),
                confidence=0.9,
                visualization=VisualizationSpec(primary="bar_ranked"),
            ),
            "Vilka produkter säljer bäst i år?",
            self.SUPPLIER,
            ui_start=self.UI_START,
            ui_end=self.UI_END,
        )
        self.assertEqual(norm.tool_plans[0].tool_name, "get_top_products")
        ytd_start, ytd_end = self._expected_ytd()
        self.assertEqual(norm.tool_plans[0].args["start_date"], ytd_start)
        self.assertNotEqual(norm.tool_plans[0].args["start_date"], self.UI_START)

    def test_market_share_lask(self):
        norm = normalize_plan(
            AnalysisPlan(
                intent="market_share",
                time_period=TimePeriod(kind="rolling_days", days=90),
                filters=AnalysisFilters(category="Läsk"),
                confidence=0.9,
                visualization=VisualizationSpec(primary="donut"),
            ),
            "Hur stor marknadsandel har vi inom Läsk?",
            "Coca-Cola Europacific Partners Sverige",
            ui_start=self.UI_START,
            ui_end=self.UI_END,
        )
        self.assertEqual(norm.tool_plans[0].tool_name, "get_market_share")
        self.assertEqual(norm.tool_plans[0].args["category_name"], "Läsk")

    def test_product_decline_30_days(self):
        norm = normalize_plan(
            AnalysisPlan(
                intent="product_decline",
                time_period=TimePeriod(kind="rolling_days", days=30),
                confidence=0.9,
            ),
            "Vilken produkt har tappat mest de senaste 30 dagarna?",
            self.SUPPLIER,
        )
        self.assertEqual(norm.tool_plans[0].tool_name, "get_declining_products")
        self.assertEqual(norm.tool_plans[0].args["days"], 30)

    def test_region_followup_stockholm(self):
        prior = PriorTurnContext(
            question="Vilka produkter säljer bäst?",
            tool_calls=("get_top_products",),
            sources=({"date_range": {"start": "2026-01-01", "end": "2026-06-22"}},),
        )
        norm = normalize_plan(
            AnalysisPlan(intent="unknown", confidence=0.3),
            "I Stockholm?",
            self.SUPPLIER,
            prior=prior,
        )
        self.assertFalse(norm.use_fallback)
        self.assertEqual(norm.tool_plans[0].tool_name, "get_top_products")
        self.assertEqual(norm.tool_plans[0].args.get("region"), "Stockholm")

    def test_low_confidence_unknown_falls_back(self):
        norm = normalize_plan(
            AnalysisPlan(intent="unknown", confidence=0.1, clarification_needed=True),
            "Berätta en historia om rymden",
            self.SUPPLIER,
        )
        self.assertTrue(norm.use_fallback)

    def test_tools_stay_in_allowlist(self):
        norm = normalize_plan(
            self._ytd_plan("sales_trend"),
            "Hur har försäljningen utvecklats i år?",
            self.SUPPLIER,
        )
        for plan in norm.tool_plans:
            self.assertIn(plan.tool_name, ALLOWED_TOOLS)
            self.assertNotIn("supplier_id", plan.args)

    def test_phrase_resolved_overrides_ui_default(self):
        norm = normalize_plan(
            AnalysisPlan(intent="sales_overview", time_period=TimePeriod(kind="unspecified"), confidence=0.85),
            "Hur ser försäljningen ut i år?",
            self.SUPPLIER,
            ui_start=self.UI_START,
            ui_end=self.UI_END,
        )
        assert norm.meta
        self.assertEqual(norm.meta.resolved_start_date, f"{date.today().year}-01-01")
        self.assertNotEqual(norm.meta.resolved_start_date, self.UI_START)

    def test_forra_are_and_full_history_preserved(self):
        prev = normalize_plan(
            AnalysisPlan(intent="sales_trend", time_period=TimePeriod(kind="previous_year"), confidence=0.9),
            "förra året",
            self.SUPPLIER,
        )
        assert prev.meta
        self.assertEqual(prev.meta.period_kind, "previous_year")
        self.assertTrue(prev.meta.resolved_start_date.endswith("-01-01"))

        full = normalize_plan(
            AnalysisPlan(intent="sales_trend", time_period=TimePeriod(kind="full_history"), confidence=0.9),
            "över hela perioden",
            self.SUPPLIER,
        )
        assert full.meta
        self.assertEqual(full.meta.period_kind, "full_history")


if __name__ == "__main__":
    unittest.main()
