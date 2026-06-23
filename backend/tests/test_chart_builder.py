import unittest
from datetime import date, timedelta

from app.services.chart_builder import build_chart, _truncate_label, _DECLINE_CHART_THRESHOLD_PCT
from app.services.period_utils import apply_sales_over_time_period_policy


class ChartBuilderTests(unittest.TestCase):
    def test_truncate_label(self):
        long_name = "Coca-Cola Zero Sugar Lemon 33 cl Extra Long Product Name"
        truncated = _truncate_label(long_name)
        self.assertLessEqual(len(truncated), 22)
        self.assertTrue(truncated.endswith("…"))

    def test_top_products_horizontal_with_tooltip(self):
        chart = build_chart("get_top_products", {
            "products": [
                {"product_name": "OLW Grillchips 275 g", "revenue": 7100},
                {"product_name": "Estrella Grillchips 275 g", "revenue": 5200},
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

    def test_widened_weekly_chart_title(self):
        result = apply_sales_over_time_period_policy({
            "granularity": "week",
            "series": [
                {"period": "2026-04-20", "revenue": 100},
                {"period": "2026-04-27", "revenue": 120},
                {"period": "2026-05-04", "revenue": 110},
            ],
            "date_range": {"start": "2026-04-20", "end": "2026-05-10"},
            "query_date_range": {"start": "2026-04-20", "end": "2026-05-10"},
            "chart_context": {
                "widened": True,
                "lookback_weeks": 8,
                "original_date_range": {"start": "2026-06-15", "end": "2026-06-21"},
            },
            "limitations": [],
        })
        chart = build_chart("get_sales_over_time", result)
        self.assertIsNotNone(chart)
        assert chart is not None
        self.assertEqual(chart["title"], "Utveckling inför senaste avslutade vecka")
        self.assertIn("8 avslutade veckor fram till och med", chart["description"])
        self.assertIn("avslutade veckor", chart["description"].lower())

    def test_direct_weekly_chart_final_point_matches_answer_week(self):
        week_mondays = [
            "2026-04-27",
            "2026-05-04",
            "2026-05-11",
            "2026-05-18",
            "2026-05-25",
            "2026-06-01",
            "2026-06-08",
            "2026-06-15",
        ]
        series = [
            {"period": monday, "revenue": 100.0 + i}
            for i, monday in enumerate(week_mondays)
        ]
        raw = {
            "granularity": "week",
            "series": series,
            "date_range": {"start": week_mondays[0], "end": "2026-06-21"},
            "query_date_range": {"start": week_mondays[0], "end": "2026-06-21"},
            "chart_context": {
                "widened": True,
                "lookback_weeks": 8,
                "original_date_range": {"start": "2026-06-15", "end": "2026-06-21"},
            },
            "limitations": [],
        }
        chart = build_chart("get_sales_over_time", raw)
        self.assertIsNotNone(chart)
        assert chart is not None
        policy = apply_sales_over_time_period_policy(raw)
        self.assertEqual(policy["date_range"]["end"], "2026-06-21")
        self.assertEqual(chart["data"][-1]["label"], "2026-06-15")
        self.assertEqual(chart["data"][-2]["label"], "2026-06-08")
        self.assertEqual(
            chart["description"],
            "8 avslutade veckor fram till och med 21 juni 2026",
        )
        self.assertEqual(
            chart["period_note"],
            "8 avslutade veckor fram till och med 21 juni 2026",
        )

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
