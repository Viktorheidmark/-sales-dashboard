"""Tests for ranking limit extraction and end-to-end top-N behavior."""

import os
import unittest
from datetime import date
from unittest.mock import patch

from app.schemas.analysis_plan import AnalysisPlan, TimePeriod, VisualizationSpec
from app.services.chart_builder import build_chart
from app.services.intent_router import plan_forced_tools
from app.services.period_utils import latest_completed_date
from app.services.plan_normalizer import normalize_plan
from app.services.ranking_limits import (
    DEFAULT_PRODUCT_RANKING_LIMIT,
    YTD_PRODUCT_RANKING_LIMIT,
    clamp_ranking_limit,
    extract_ranking_limit,
    resolve_product_ranking_limit,
)
from app.services.tool_planner import resolve_tool_plans


class RankingLimitExtractionTests(unittest.TestCase):
    def test_top_3_phrases(self):
        for phrase in (
            "Ge mig top 3 bästa produkterna i år",
            "topp 3 produkter",
            "de tre bästa produkterna",
            "tre bästa produkterna",
            "3 bästa produkter",
            "vilka är de 3 bästa",
        ):
            with self.subTest(phrase=phrase):
                self.assertEqual(extract_ranking_limit(phrase), 3)

    def test_other_explicit_limits(self):
        self.assertEqual(extract_ranking_limit("Vilka är de fem bästa produkterna?"), 5)
        self.assertEqual(extract_ranking_limit("Visa topp 10 produkter"), 10)
        self.assertEqual(extract_ranking_limit("Visa 4 produkter"), 4)
        self.assertEqual(extract_ranking_limit("Vilka är de 2 bästa"), 2)

    def test_no_limit_returns_none(self):
        self.assertIsNone(extract_ranking_limit("Vilka produkter säljer bäst i år?"))

    def test_clamp_to_max_10(self):
        self.assertEqual(clamp_ranking_limit(25), 10)
        self.assertEqual(clamp_ranking_limit(0), 1)


class RankingLimitRoutingTests(unittest.TestCase):
    UI_START = "2026-03-25"
    UI_END = "2026-06-23"
    SUPPLIER = "Orkla Snacks Sverige"

    def _expected_ytd(self) -> tuple[str, str]:
        return f"{date.today().year}-01-01", latest_completed_date().isoformat()

    def test_ytd_top_3_legacy_routing(self):
        plans = plan_forced_tools(
            "Ge mig top 3 bästa produkterna i år",
            self.SUPPLIER,
            start_date=self.UI_START,
            end_date=self.UI_END,
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_top_products")
        self.assertEqual(plans[0].args["limit"], 3)
        ytd_start, ytd_end = self._expected_ytd()
        self.assertEqual(plans[0].args["start_date"], ytd_start)
        self.assertEqual(plans[0].args["end_date"], ytd_end)

    def test_fem_basta_limit_5(self):
        plans = plan_forced_tools(
            "Vilka är de fem bästa produkterna?",
            self.SUPPLIER,
        )
        self.assertEqual(plans[0].args["limit"], 5)

    def test_topp_10_limit_10(self):
        plans = plan_forced_tools(
            "Visa topp 10 produkter",
            self.SUPPLIER,
        )
        self.assertEqual(plans[0].args["limit"], 10)

    def test_ytd_without_n_uses_ytd_default(self):
        plans = plan_forced_tools(
            "Vilka produkter säljer bäst i år?",
            self.SUPPLIER,
            start_date=self.UI_START,
            end_date=self.UI_END,
        )
        self.assertEqual(plans[0].args["limit"], YTD_PRODUCT_RANKING_LIMIT)

    def test_non_ytd_without_n_uses_default(self):
        plans = plan_forced_tools(
            "Vilka produkter säljer bäst?",
            self.SUPPLIER,
        )
        self.assertEqual(plans[0].args["limit"], DEFAULT_PRODUCT_RANKING_LIMIT)

    def test_region_ranking_unchanged(self):
        plans = plan_forced_tools(
            "Vilken region genererar mest intäkter?",
            "Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(plans[0].tool_name, "get_sales_by_region")
        self.assertNotIn("limit", plans[0].args)

    def test_market_share_unchanged(self):
        plans = plan_forced_tools(
            "Hur stor marknadsandel har vi inom Läsk?",
            "Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(plans[0].tool_name, "get_market_share")


class RankingLimitPlannerTests(unittest.TestCase):
    UI_START = "2026-03-25"
    UI_END = "2026-06-23"
    SUPPLIER = "Orkla Snacks Sverige"

    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"USE_AI_PLANNER": "true"})
        self._env_patch.start()

    def tearDown(self):
        self._env_patch.stop()

    def test_planner_limit_preserved_in_tool_args(self):
        plan = AnalysisPlan(
            intent="product_ranking",
            time_period=TimePeriod(kind="year_to_date"),
            limit=3,
            confidence=0.95,
            visualization=VisualizationSpec(primary="bar_ranked"),
        )
        res = resolve_tool_plans(
            "Ge mig top 3 bästa produkterna i år",
            self.SUPPLIER,
            self.UI_START,
            self.UI_END,
            injected_plan=plan,
        )
        self.assertEqual(res.source, "planner")
        top_plan = next(p for p in res.plans if p.tool_name == "get_top_products")
        self.assertEqual(top_plan.args["limit"], 3)

    def test_message_limit_overrides_planner_default(self):
        norm = normalize_plan(
            AnalysisPlan(
                intent="product_ranking",
                time_period=TimePeriod(kind="year_to_date"),
                limit=10,
                confidence=0.9,
            ),
            "Ge mig top 3 bästa produkterna i år",
            self.SUPPLIER,
        )
        self.assertEqual(norm.tool_plans[0].args["limit"], 3)

    def test_chart_and_list_exactly_n_items(self):
        products = [
            {"product_name": f"Produkt {i}", "revenue": float(100 - i)}
            for i in range(1, 6)
        ]
        result = {
            "products": products[:3],
            "requested_limit": 3,
            "date_range": {"start": "2026-01-01", "end": "2026-06-23"},
        }
        chart = build_chart("get_top_products", result)
        assert chart is not None
        self.assertEqual(len(chart["data"]), 3)
        self.assertEqual(chart["generated_from_row_count"], 3)
        self.assertEqual(len(result["products"]), 3)


if __name__ == "__main__":
    unittest.main()
