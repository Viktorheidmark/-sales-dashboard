import unittest

from app.services.deep_dive_builder import build_deep_dive, build_follow_up_actions
from app.services.chart_policy import select_charts


class DeepDiveBuilderTests(unittest.TestCase):
    def _drivers_result(self) -> dict:
        return {
            "comparison_days": 30,
            "current_period": {
                "start": "2026-05-24",
                "end": "2026-06-23",
                "total_revenue": 120000.0,
                "total_orders": 48,
                "total_units": 320,
            },
            "prior_period": {
                "start": "2026-04-24",
                "end": "2026-05-23",
                "total_revenue": 100000.0,
                "total_orders": 40,
                "total_units": 280,
            },
            "gainers": [
                {
                    "rank": 1,
                    "product_name": "Produkt A",
                    "current_period_revenue": 50000.0,
                    "prior_period_revenue": 40000.0,
                    "revenue_change": 10000.0,
                    "revenue_change_pct": 25.0,
                },
            ],
            "losers": [
                {
                    "rank": 1,
                    "product_name": "Produkt B",
                    "current_period_revenue": 20000.0,
                    "prior_period_revenue": 30000.0,
                    "revenue_change": -10000.0,
                    "revenue_change_pct": -33.3,
                },
            ],
            "region_gainers": [
                {
                    "rank": 1,
                    "region": "Stockholm",
                    "current_period_revenue": 60000.0,
                    "prior_period_revenue": 50000.0,
                    "revenue_change": 10000.0,
                    "revenue_change_pct": 20.0,
                },
            ],
            "region_losers": [
                {
                    "rank": 1,
                    "region": "Malmö",
                    "current_period_revenue": 15000.0,
                    "prior_period_revenue": 20000.0,
                    "revenue_change": -5000.0,
                    "revenue_change_pct": -25.0,
                },
            ],
        }

    def test_revenue_development_deep_dive(self):
        deep = build_deep_dive([("get_revenue_drivers", self._drivers_result())])
        self.assertIsNotNone(deep)
        assert deep is not None
        self.assertEqual(deep["kind"], "revenue_development")
        summary = deep["period_summary"]
        self.assertAlmostEqual(summary["revenue_change"], 20000.0)
        self.assertAlmostEqual(summary["revenue_change_pct"], 20.0)
        self.assertEqual(summary["orders_change"], 8)
        self.assertEqual(len(deep["top_gainers"]), 1)
        self.assertEqual(deep["strongest_region"]["region"], "Stockholm")
        self.assertEqual(deep["weakest_region"]["region"], "Malmö")

    def test_product_decline_deep_dive(self):
        declining = {
            "comparison_days": 30,
            "latest_period": {"start": "2026-05-24", "end": "2026-06-23"},
            "prior_period": {"start": "2026-04-24", "end": "2026-05-23"},
            "products": [
                {
                    "rank": 1,
                    "product_name": "OLW Grillchips",
                    "latest_period_revenue": 8500.0,
                    "prior_period_revenue": 14650.0,
                    "revenue_change": -6150.0,
                    "revenue_change_pct": -42.0,
                    "latest_period_orders": 12,
                    "prior_period_orders": 20,
                    "latest_period_units": 90,
                    "prior_period_units": 150,
                },
            ],
            "focus_product_regions": [
                {
                    "rank": 1,
                    "region": "Göteborg",
                    "current_period_revenue": 3000.0,
                    "prior_period_revenue": 6000.0,
                    "revenue_change": -3000.0,
                    "revenue_change_pct": -50.0,
                },
            ],
            "focus_product_weekly_series": [
                {"period": "2026-05-05", "revenue": 4000.0},
                {"period": "2026-05-12", "revenue": 3500.0},
                {"period": "2026-05-19", "revenue": 2500.0},
            ],
        }
        deep = build_deep_dive([("get_declining_products", declining)])
        self.assertIsNotNone(deep)
        assert deep is not None
        self.assertEqual(deep["kind"], "product_decline")
        self.assertEqual(deep["focus_product"]["product_name"], "OLW Grillchips")
        self.assertEqual(deep["period_summary"]["orders_change"], -8)

    def test_follow_up_actions_revenue(self):
        deep = build_deep_dive([("get_revenue_drivers", self._drivers_result())])
        actions = build_follow_up_actions(deep)
        labels = [a["label"] for a in actions]
        self.assertIn("Visa vilka produkter som driver utvecklingen", labels)
        self.assertIn("Visa utveckling per region", labels)

    def test_30_day_trend_question_uses_line_chart_primary(self):
        q = "Hur har försäljningen utvecklats de senaste 30 dagarna?"
        flat_series = {
            "granularity": "week",
            "_force_time_series": True,
            "series": [
                {"period": "2026-05-05", "revenue": 25000.0},
                {"period": "2026-05-12", "revenue": 25100.0},
                {"period": "2026-05-19", "revenue": 24900.0},
            ],
        }
        charts = select_charts(q, [
            ("get_revenue_drivers", self._drivers_result()),
            ("get_sales_over_time", flat_series),
        ])
        self.assertEqual(charts[0]["chart_type"], "line_chart")
        self.assertIn("stability_note", charts[0])


if __name__ == "__main__":
    unittest.main()
