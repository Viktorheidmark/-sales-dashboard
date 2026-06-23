"""Unit tests for incomplete-period filtering."""

import unittest
from datetime import date

from app.services.period_utils import (
    apply_sales_over_time_period_policy,
    completed_week_bounds,
    completed_week_label,
    current_period_start,
    filter_incomplete_series,
    format_week_range_sv,
    series_date_range,
)


class PeriodUtilsTests(unittest.TestCase):
    def test_current_month_start(self):
        ref = date(2026, 6, 23)
        self.assertEqual(current_period_start("month", ref), "2026-06-01")

    def test_completed_week_bounds(self):
        ref = date(2026, 6, 22)  # Monday — new week just started
        mon, sun = completed_week_bounds(ref)
        self.assertEqual(mon, date(2026, 6, 15))
        self.assertEqual(sun, date(2026, 6, 21))

    def test_completed_week_bounds_midweek(self):
        ref = date(2026, 6, 25)  # Thursday — current week Mon 22 is in progress
        mon, sun = completed_week_bounds(ref)
        self.assertEqual(mon, date(2026, 6, 15))
        self.assertEqual(sun, date(2026, 6, 21))

    def test_format_week_range_sv(self):
        self.assertEqual(
            format_week_range_sv(date(2026, 6, 16)),
            "16–22 juni 2026",
        )

    def test_excludes_incomplete_month_from_series(self):
        series = [
            {"period": "2026-04-01", "revenue": 100.0},
            {"period": "2026-05-01", "revenue": 110.0},
            {"period": "2026-06-01", "revenue": 20.0},
        ]
        ref = date(2026, 6, 23)
        completed, meta = filter_incomplete_series(series, "month", ref)
        self.assertEqual(len(completed), 2)
        self.assertEqual(completed[-1]["period"], "2026-05-01")
        self.assertTrue(meta.get("excluded_incomplete_period"))
        self.assertIn("exkluderats", meta.get("analysis_note", ""))

    def test_excludes_incomplete_week_without_long_note(self):
        series = [
            {"period": "2026-06-16", "revenue": 100.0, "orders": 10, "units": 50},
            {"period": "2026-06-23", "revenue": 20.0, "orders": 2, "units": 5},
        ]
        ref = date(2026, 6, 25)
        completed, meta = filter_incomplete_series(series, "week", ref)
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0]["period"], "2026-06-16")
        self.assertTrue(meta.get("excluded_incomplete_period"))
        self.assertNotIn("analysis_note", meta)
        self.assertEqual(meta.get("completed_week_label"), completed_week_label("2026-06-16"))

    def test_apply_policy_aligns_date_range(self):
        result = {
            "granularity": "week",
            "series": [
                {"period": "2026-06-16", "revenue": 100.0, "orders": 10, "units": 50},
                {"period": "2026-06-23", "revenue": 20.0, "orders": 2, "units": 5},
            ],
            "date_range": {"start": "2026-06-16", "end": "2026-06-25"},
            "limitations": [],
        }
        out = apply_sales_over_time_period_policy(result)
        self.assertEqual(len(out["series"]), 1)
        self.assertEqual(out["date_range"], {"start": "2026-06-16", "end": "2026-06-22"})
        self.assertIn("completed_week_label", out)

    def test_apply_policy_adds_analysis_note(self):
        result = {
            "granularity": "month",
            "series": [
                {"period": "2026-05-01", "revenue": 110.0},
                {"period": "2026-06-01", "revenue": 20.0},
            ],
            "limitations": [],
        }
        out = apply_sales_over_time_period_policy(result)
        self.assertEqual(len(out["series"]), 1)
        self.assertIn("analysis_note", out)
        self.assertTrue(any("exkluderats" in l for l in out["limitations"]))

    def test_series_date_range_week(self):
        series = [{"period": "2026-06-16", "revenue": 1}]
        self.assertEqual(
            series_date_range(series, "week"),
            {"start": "2026-06-16", "end": "2026-06-22"},
        )


if __name__ == "__main__":
    unittest.main()
