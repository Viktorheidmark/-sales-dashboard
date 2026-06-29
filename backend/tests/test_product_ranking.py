"""Regression tests for ascending vs descending product ranking."""

import unittest

from app.analytics import planner as analytics_planner
from app.services.chart_builder import build_chart
from app.services.intent_router import plan_forced_tools
from app.services.period_labels import apply_period_labels
from app.services.period_utils import default_data_bounds
from app.services.ranking_limits import (
    ASCENDING_PRODUCT_RANKING_TITLE,
    is_ascending_product_ranking_question,
)
from app.services.response_guidance import synthesis_blueprint


class ProductRankingPresentationTests(unittest.TestCase):
    SUPPLIER = "Coca-Cola Europacific Partners Sverige"

    def _ascending_products(self) -> list[dict]:
        """Demo-like ascending order (lowest revenue first)."""
        return [
            {"product_name": "Sprite Zero Sugar 33 cl", "revenue": 1200.0, "units": 40, "rank": 1},
            {"product_name": "Fanta Zero Orange 33 cl", "revenue": 2100.0, "units": 55, "rank": 2},
            {"product_name": "Sprite 33 cl", "revenue": 3400.0, "units": 70, "rank": 3},
            {"product_name": "Coca-Cola Zero Sugar Lemon 33 cl", "revenue": 4100.0, "units": 80, "rank": 4},
            {"product_name": "Fanta Orange 33 cl", "revenue": 5200.0, "units": 95, "rank": 5},
        ]

    def test_lowest_revenue_question_routes_ascending_ranking(self):
        q = "Vilka produkter har lägst omsättning?"
        self.assertTrue(is_ascending_product_ranking_question(q))
        self.assertIsNone(analytics_planner.plan_comparison(q))

        plans = plan_forced_tools(q, self.SUPPLIER, None, None)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_top_products")
        self.assertEqual(plans[0].args.get("sort_order"), "asc")
        self.assertNotIn("get_declining_products", [p.tool_name for p in plans])

    def test_lowest_revenue_chart_is_ascending_with_correct_title(self):
        q = "Vilka produkter har lägst omsättning?"
        # Use live data bounds so the range always equals the full-history sentinel.
        # _kind_from_date_span returns "full_history" only when start/end match
        # default_data_bounds() exactly; hardcoding dates breaks as today rolls forward.
        data_min, data_max = default_data_bounds()
        payload = apply_period_labels({
            "products": self._ascending_products(),
            "requested_limit": 5,
            "sort_order": "asc",
            "date_range": {"start": data_min.isoformat(), "end": data_max.isoformat()},
        }, q, tool_name="get_top_products")

        chart = build_chart("get_top_products", payload)
        self.assertIsNotNone(chart)
        assert chart is not None
        self.assertEqual(chart["title"], ASCENDING_PRODUCT_RANKING_TITLE)
        self.assertNotEqual(chart["title"], "Topprodukter")
        self.assertEqual(chart["ranking_direction"], "ascending")
        self.assertIn("hela tillgängliga perioden", chart["description"])

        revenues = [row["revenue"] for row in chart["data"]]
        self.assertEqual(revenues, sorted(revenues))
        self.assertEqual(chart["data"][0]["product_name"], "Sprite Zero Sugar 33 cl")
        self.assertLess(revenues[0], revenues[-1])

    def test_lowest_revenue_synthesis_guidance_is_grounded(self):
        q = "Vilka produkter har lägst omsättning?"
        block = synthesis_blueprint(
            q,
            ["get_top_products"],
            self.SUPPLIER,
        )
        self.assertIn("lägst omsättning", block.lower())
        self.assertIn("distribution, volym och utveckling över tid", block)
        self.assertIn("undvik starka slutsatser", block.lower())

    def test_best_sellers_keep_descending_topprodukter(self):
        q = "Vilka produkter säljer bäst?"
        self.assertFalse(is_ascending_product_ranking_question(q))
        plans = plan_forced_tools(q, self.SUPPLIER, None, None)
        self.assertEqual(plans[0].tool_name, "get_top_products")
        self.assertNotEqual(plans[0].args.get("sort_order"), "asc")

        payload = {
            "products": list(reversed(self._ascending_products())),
            "requested_limit": 5,
            "sort_order": "desc",
            "date_range": {"start": "2024-06-28", "end": "2026-06-27"},
        }
        chart = build_chart("get_top_products", payload)
        self.assertIsNotNone(chart)
        assert chart is not None
        self.assertEqual(chart["title"], "Topprodukter")
        self.assertEqual(chart["ranking_direction"], "descending")
        revenues = [row["revenue"] for row in chart["data"]]
        self.assertEqual(revenues, sorted(revenues, reverse=True))

    def test_low_revenue_wording_never_routes_to_decline(self):
        for q in (
            "Vilka produkter har lägst omsättning?",
            "Vilka produkter säljer sämst?",
            "Vilka produkter har minst försäljning?",
        ):
            with self.subTest(q=q):
                self.assertTrue(is_ascending_product_ranking_question(q))
                plans = plan_forced_tools(q, self.SUPPLIER, None, None)
                self.assertEqual(plans[0].tool_name, "get_top_products")
                self.assertNotEqual(plans[0].tool_name, "get_declining_products")


if __name__ == "__main__":
    unittest.main()
