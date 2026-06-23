import unittest
from datetime import date, timedelta

from app.services.chart_builder import build_chart, _truncate_label, _compute_highlights, _DECLINE_CHART_THRESHOLD_PCT
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
        # Only "Big Drop" passes the -5 % threshold → 1 product → comparison bar chart
        chart = build_chart("get_declining_products", {
            "comparison_days": 30,
            "products": [
                {
                    "product_name": "Big Drop",
                    "revenue_change_pct": -25.0,
                    "latest_period_revenue": 5000.0,
                    "prior_period_revenue": 20000.0,
                    "revenue_change": -15000.0,
                },
                {"product_name": "Flat Product", "revenue_change_pct": -1.0},
                {"product_name": "Tiny Dip", "revenue_change_pct": _DECLINE_CHART_THRESHOLD_PCT + 0.5},
            ],
        })
        self.assertIsNotNone(chart)
        assert chart is not None
        self.assertEqual(chart["chart_type"], "bar_chart")
        self.assertEqual(chart["chart_variant"], "decline_comparison")
        self.assertEqual(chart["title"], "Big Drop")
        self.assertEqual(len(chart["data"]), 2)  # prior + current

    def test_declining_one_product_returns_comparison_chart(self):
        chart = build_chart("get_declining_products", {
            "comparison_days": 30,
            "products": [
                {
                    "product_name": "OLW Jordnötsringar 175 g",
                    "revenue_change_pct": -42.0,
                    "latest_period_revenue": 8500.0,
                    "prior_period_revenue": 14650.0,
                    "revenue_change": -6150.0,
                },
            ],
        })
        self.assertIsNotNone(chart)
        assert chart is not None
        self.assertEqual(chart["chart_type"], "bar_chart")
        self.assertEqual(chart["chart_variant"], "decline_comparison")
        self.assertEqual(chart["generated_from_row_count"], 1)
        self.assertEqual(chart["title"], "OLW Jordnötsringar 175 g")
        self.assertIn("42", chart["description"])  # pct in description
        labels = [row["period"] for row in chart["data"]]
        self.assertIn("Föregående period", labels)
        self.assertIn("Senaste period", labels)
        prior_row = next(r for r in chart["data"] if r["period"] == "Föregående period")
        current_row = next(r for r in chart["data"] if r["period"] == "Senaste period")
        self.assertAlmostEqual(prior_row["revenue"], 14650.0)
        self.assertAlmostEqual(current_row["revenue"], 8500.0)

    def test_declining_two_plus_products_returns_ranked_bar_chart(self):
        chart = build_chart("get_declining_products", {
            "comparison_days": 30,
            "products": [
                {"product_name": "Produkt A", "revenue_change_pct": -25.0},
                {"product_name": "Produkt B", "revenue_change_pct": -15.0},
            ],
        })
        self.assertIsNotNone(chart)
        assert chart is not None
        self.assertEqual(chart["chart_type"], "bar_chart")
        self.assertEqual(chart["layout"], "horizontal")
        self.assertEqual(len(chart["data"]), 2)
        self.assertEqual(chart["data"][0]["product_name"], "Produkt A")

    def test_declining_zero_products_returns_empty_state(self):
        chart = build_chart("get_declining_products", {
            "comparison_days": 30,
            "products": [],
        })
        self.assertIsNotNone(chart)
        assert chart is not None
        self.assertEqual(chart["chart_type"], "empty_state")
        self.assertEqual(chart["generated_from_row_count"], 0)
        self.assertIn("stabila", chart["description"])

    def test_declining_all_flat_products_returns_empty_state(self):
        # All products above threshold → filtered out → empty_state
        chart = build_chart("get_declining_products", {
            "comparison_days": 30,
            "products": [
                {"product_name": "Flat A", "revenue_change_pct": -1.0},
                {"product_name": "Flat B", "revenue_change_pct": -2.0},
            ],
        })
        self.assertIsNotNone(chart)
        assert chart is not None
        self.assertEqual(chart["chart_type"], "empty_state")

    def test_trend_chart_includes_highlights(self):
        result = {
            "granularity": "week",
            "_force_time_series": True,
            "series": [
                {"period": "2026-05-05", "revenue": 30000.0},
                {"period": "2026-05-12", "revenue": 45000.0},
                {"period": "2026-05-19", "revenue": 38000.0},
                {"period": "2026-05-26", "revenue": 42000.0},
            ],
            "date_range": {"start": "2026-05-05", "end": "2026-06-01"},
            "query_date_range": {"start": "2026-05-05", "end": "2026-06-01"},
            "limitations": [],
        }
        chart = build_chart("get_sales_over_time", result)
        self.assertIsNotNone(chart)
        assert chart is not None
        self.assertIn("highlights", chart)
        h = chart["highlights"]
        self.assertEqual(h["peak_label"], "2026-05-12")
        self.assertAlmostEqual(h["peak_revenue"], 45000.0)
        self.assertEqual(h["trough_label"], "2026-05-05")
        self.assertAlmostEqual(h["trough_revenue"], 30000.0)
        self.assertAlmostEqual(h["first_revenue"], 30000.0)
        self.assertAlmostEqual(h["last_revenue"], 42000.0)
        self.assertGreater(h["change_pct"], 0)  # grew from 30k to 42k

    def test_small_trend_dataset_no_chart(self):
        # Fewer than 2 usable data points → chart builder returns None
        result = {
            "granularity": "week",
            "series": [{"period": "2026-05-05", "revenue": 30000.0}],
            "date_range": {"start": "2026-05-05", "end": "2026-05-11"},
            "query_date_range": {"start": "2026-05-05", "end": "2026-05-11"},
            "limitations": [],
        }
        chart = build_chart("get_sales_over_time", result)
        self.assertIsNone(chart)

    def test_compute_highlights_direct(self):
        data = [
            {"label": "v1", "revenue": 100.0},
            {"label": "v2", "revenue": 200.0},
            {"label": "v3", "revenue": 150.0},
        ]
        h = _compute_highlights(data)
        self.assertIsNotNone(h)
        assert h is not None
        self.assertEqual(h["peak_label"], "v2")
        self.assertEqual(h["trough_label"], "v1")
        self.assertAlmostEqual(h["change_pct"], 50.0)  # 100 → 150

    def test_compute_highlights_too_short_returns_none(self):
        self.assertIsNone(_compute_highlights([]))
        self.assertIsNone(_compute_highlights([{"label": "v1", "revenue": 100.0}]))

    def test_widened_weekly_chart_title(self):
        result = apply_sales_over_time_period_policy({
            "granularity": "week",
            "_force_time_series": True,
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
            "_force_time_series": True,
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
            "_force_time_series": True,
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
