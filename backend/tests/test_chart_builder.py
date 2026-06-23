import unittest
from datetime import date, timedelta

from app.services.chart_builder import build_chart, _truncate_label, _DECLINE_CHART_THRESHOLD_PCT
from app.services.period_utils import apply_sales_over_time_period_policy


class ChartBuilderTests(unittest.TestCase):
    def test_truncate_label(self):
        long_name = "Arla Proteindryck Vanilj 500ml Extra Long Product Name"
        truncated = _truncate_label(long_name)
        self.assertLessEqual(len(truncated), 22)
        self.assertTrue(truncated.endswith("…"))

    def test_top_products_horizontal_with_tooltip(self):
        chart = build_chart("get_top_products", {
            "products": [
                {"product_name": "KESO Cottage Cheese", "revenue": 7100},
                {"product_name": "Arla Mellanmjölk 1,5%", "revenue": 5200},
            ],
        })
        self.assertIsNotNone(chart)
        assert chart is not None
        self.assertEqual(chart["layout"], "horizontal")
        self.assertEqual(chart["tooltip_key"], "product_name")
        self.assertEqual(chart["emphasis_index"], 0)
        self.assertIn("display_label", chart["data"][0])

    def test_declining_products_filters_flat_changes(self):
        chart = build_chart("get_declining_products", {
            "comparison_days": 30,
            "products": [
                {"product_name": "Big Drop", "revenue_change_pct": -25.0},
                {"product_name": "Flat Product", "revenue_change_pct": -1.0},
                {"product_name": "Tiny Dip", "revenue_change_pct": _DECLINE_CHART_THRESHOLD_PCT + 0.5},
            ],
        })
        self.assertIsNotNone(chart)
        assert chart is not None
        names = [row["product_name"] for row in chart["data"]]
        self.assertEqual(names, ["Big Drop"])
        self.assertEqual(chart["layout"], "horizontal")

    def test_sales_over_time_period_note_when_incomplete(self):
        today = date.today()
        period_start = today.replace(day=1).isoformat()
        result = apply_sales_over_time_period_policy({
            "granularity": "month",
            "series": [
                {"period": "2026-04-01", "revenue": 100},
                {"period": "2026-05-01", "revenue": 120},
                {"period": period_start, "revenue": 50},
            ],
            "date_range": {"start": "2026-04-01", "end": today.isoformat()},
            "limitations": [],
        })
        chart = build_chart("get_sales_over_time", result)
        self.assertIsNotNone(chart)
        assert chart is not None
        self.assertIsNotNone(chart.get("period_note"))
        self.assertEqual(len(chart["data"]), 2)


if __name__ == "__main__":
    unittest.main()
