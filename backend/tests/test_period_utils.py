"""Unit tests for incomplete-period filtering."""

import unittest
from datetime import date

from app.services.period_utils import (
    align_weekly_query_bounds,
    apply_sales_over_time_period_policy,
    completed_week_bounds,
    completed_week_label,
    current_period_start,
    current_year_period_range,
    default_data_bounds,
    filter_incomplete_series,
    first_complete_week_monday,
    format_week_range_sv,
    format_compact_date_range_sv,
    format_week_series_label_sv,
    is_current_year_phrase,
    latest_completed_date,
    resolve_period_range,
    series_date_range,
)


class PeriodUtilsTests(unittest.TestCase):
    REF = date(2026, 6, 23)
    DATA_MIN = date(2024, 6, 24)
    DATA_MAX = date(2026, 6, 22)

    def test_latest_completed_date(self):
        self.assertEqual(latest_completed_date(self.REF), date(2026, 6, 22))

    def test_detta_ar_resolves_ytd(self):
        out = resolve_period_range(
            "Jämför försäljningen över detta år",
            reference=self.REF,
            data_min=self.DATA_MIN,
            data_max=self.DATA_MAX,
        )
        self.assertEqual(out["start_date"], "2026-01-01")
        self.assertEqual(out["end_date"], "2026-06-22")
        self.assertEqual(out.get("period_kind"), "current_year")

    def test_i_ar_resolves_same_as_detta_ar(self):
        phrases = [
            "i år",
            "hittills i år",
            "Hur ser försäljningen ut i år?",
            "Hur ser försäljningen överlag ut detta år?",
            "Hur har försäljningen utvecklats i år?",
            "Vilka produkter säljer bäst i år?",
            "under året",
            "årets försäljning",
        ]
        expected = current_year_period_range(
            reference=self.REF,
            data_min=self.DATA_MIN,
            data_max=self.DATA_MAX,
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertTrue(is_current_year_phrase(phrase))
                out = resolve_period_range(
                    phrase,
                    reference=self.REF,
                    data_min=self.DATA_MIN,
                    data_max=self.DATA_MAX,
                )
                self.assertEqual(out["start_date"], expected["start_date"])
                self.assertEqual(out["end_date"], expected["end_date"])

    def test_forra_are_resolves_previous_calendar_year(self):
        out = resolve_period_range(
            "förra året",
            reference=self.REF,
            data_min=self.DATA_MIN,
            data_max=self.DATA_MAX,
        )
        self.assertEqual(out["start_date"], "2025-01-01")
        self.assertEqual(out["end_date"], "2025-12-31")

    def test_over_hela_perioden_resolves_full_dataset(self):
        out = resolve_period_range(
            "över hela perioden",
            reference=self.REF,
            data_min=self.DATA_MIN,
            data_max=self.DATA_MAX,
        )
        self.assertEqual(out["start_date"], self.DATA_MIN.isoformat())
        self.assertEqual(out["end_date"], self.DATA_MAX.isoformat())

    def test_senaste_30_dagar_ends_on_latest_completed(self):
        out = resolve_period_range(
            "senaste 30 dagarna",
            reference=self.REF,
            data_min=self.DATA_MIN,
            data_max=self.DATA_MAX,
        )
        self.assertEqual(out["end_date"], "2026-06-22")
        self.assertEqual(out["start_date"], "2026-05-24")

    def test_senaste_90_dagar_unchanged_shape(self):
        out = resolve_period_range(
            "senaste 90 dagarna",
            reference=self.REF,
            data_min=self.DATA_MIN,
            data_max=self.DATA_MAX,
        )
        self.assertEqual(out["days"], 90)
        self.assertEqual(out["end_date"], "2026-06-22")

    def test_default_data_bounds_two_year_window(self):
        start, end = default_data_bounds(self.REF)
        self.assertEqual(end, date(2026, 6, 22))
        self.assertEqual((end - start).days + 1, 730)

    def test_ytd_monthly_chart_excludes_incomplete_current_month(self):
        result = {
            "granularity": "month",
            "series": [
                {"period": "2026-01-01", "revenue": 100.0},
                {"period": "2026-02-01", "revenue": 110.0},
                {"period": "2026-03-01", "revenue": 120.0},
                {"period": "2026-04-01", "revenue": 130.0},
                {"period": "2026-05-01", "revenue": 140.0},
                {"period": "2026-06-01", "revenue": 20.0},
            ],
            "date_range": {"start": "2026-01-01", "end": "2026-06-22"},
            "query_date_range": {"start": "2026-01-01", "end": "2026-06-22"},
            "limitations": [],
        }
        out = apply_sales_over_time_period_policy(result)
        self.assertEqual(len(out["series"]), 5)
        self.assertEqual(out["series"][-1]["period"], "2026-05-01")
        self.assertTrue(out.get("period_analysis", {}).get("excluded_incomplete_period"))

    def test_current_month_start(self):
        ref = date(2026, 6, 23)
        self.assertEqual(current_period_start("month", ref), "2026-06-01")

    def test_first_complete_week_monday(self):
        self.assertEqual(first_complete_week_monday(date(2026, 5, 24)), date(2026, 5, 25))
        self.assertEqual(first_complete_week_monday(date(2026, 5, 25)), date(2026, 5, 25))

    def test_align_weekly_query_bounds(self):
        ref = date(2026, 6, 25)
        aligned = align_weekly_query_bounds("2026-05-24", "2026-06-25", ref)
        self.assertEqual(aligned["start"], "2026-05-25")
        self.assertEqual(aligned["end"], "2026-06-21")

    def test_excludes_partial_start_week(self):
        series = [
            {"period": "2026-05-18", "revenue": 50.0},
            {"period": "2026-05-25", "revenue": 100.0},
            {"period": "2026-06-01", "revenue": 110.0},
            {"period": "2026-06-22", "revenue": 20.0},
        ]
        ref = date(2026, 6, 25)
        completed, meta = filter_incomplete_series(
            series, "week", ref, query_start="2026-05-24",
        )
        self.assertEqual(completed[0]["period"], "2026-05-25")
        self.assertTrue(meta.get("excluded_partial_start_week"))
        self.assertEqual(completed[-1]["period"], "2026-06-01")

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

    def test_completed_week_bounds_sunday_reference_is_week_before(self):
        """A completed Sunday must not be passed as reference — it shifts back one week."""
        mon, sun = completed_week_bounds(date(2026, 6, 21))
        self.assertEqual(mon, date(2026, 6, 8))
        self.assertEqual(sun, date(2026, 6, 14))

    def test_format_week_range_sv(self):
        self.assertEqual(
            format_week_range_sv(date(2026, 6, 15)),
            "15–21 juni",
        )

    def test_format_compact_date_range_same_month(self):
        self.assertEqual(
            format_compact_date_range_sv("2026-06-09", "2026-06-15"),
            "9–15 juni",
        )

    def test_format_compact_date_range_cross_month(self):
        self.assertEqual(
            format_compact_date_range_sv("2026-03-30", "2026-04-05"),
            "30 mars–5 april",
        )

    def test_format_compact_date_range_cross_year(self):
        self.assertEqual(
            format_compact_date_range_sv("2025-12-30", "2026-01-05"),
            "30 dec 2025–5 jan 2026",
        )

    def test_full_iso_week_label(self):
        self.assertEqual(
            format_week_series_label_sv("2026-03-30"),
            "veckan 30 mars–5 april",
        )

    def test_partial_week_label(self):
        self.assertEqual(
            format_week_series_label_sv("2026-03-23", "2026-03-27"),
            "perioden 27–29 mars",
        )

    def test_weekly_series_enriched_with_period_label(self):
        series = [
            {"period": "2026-03-30", "revenue": 100.0},
            {"period": "2026-04-06", "revenue": 110.0},
        ]
        out = apply_sales_over_time_period_policy({
            "granularity": "week",
            "series": series,
            "date_range": {"start": "2026-03-30", "end": "2026-04-12"},
            "query_date_range": {"start": "2026-03-30", "end": "2026-04-12"},
            "limitations": [],
        })
        self.assertEqual(out["series"][0]["period_label"], "veckan 30 mars–5 april")
        self.assertNotIn("…", out["series"][0]["period_label"])

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
            {"period": "2026-06-15", "revenue": 100.0, "orders": 10, "units": 50},
            {"period": "2026-06-22", "revenue": 20.0, "orders": 2, "units": 5},
        ]
        ref = date(2026, 6, 25)
        completed, meta = filter_incomplete_series(series, "week", ref)
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0]["period"], "2026-06-15")
        self.assertTrue(meta.get("excluded_incomplete_period"))
        self.assertNotIn("analysis_note", meta)
        self.assertEqual(meta.get("completed_week_label"), completed_week_label("2026-06-15"))

    def test_apply_policy_aligns_date_range(self):
        result = {
            "granularity": "week",
            "series": [
                {"period": "2026-06-15", "revenue": 100.0, "orders": 10, "units": 50},
                {"period": "2026-06-22", "revenue": 20.0, "orders": 2, "units": 5},
            ],
            "date_range": {"start": "2026-06-15", "end": "2026-06-25"},
            "query_date_range": {"start": "2026-06-15", "end": "2026-06-25"},
            "limitations": [],
        }
        out = apply_sales_over_time_period_policy(result)

        # Policy contract: no in-progress week may appear in the output.
        # current_period_start returns this week's Monday (live); every output
        # period must be strictly before it.
        this_week_monday = current_period_start("week")
        for row in out["series"]:
            self.assertLess(
                str(row["period"])[:10],
                this_week_monday,
                f"Week {row['period']} should have been stripped as incomplete",
            )

        # The week of 2026-06-15 is always in the past and must always be retained.
        retained_periods = [str(r["period"])[:10] for r in out["series"]]
        self.assertIn("2026-06-15", retained_periods)

        # date_range end must be a Sunday (week-aligned to the last complete week).
        end_date = date.fromisoformat(out["date_range"]["end"])
        self.assertEqual(end_date.weekday(), 6, "date_range end must be a Sunday")
        self.assertEqual(out["date_range"]["start"], "2026-06-15")

        # completed_week_label must be present for any weekly result.
        self.assertIn("completed_week_label", out)

    def test_single_completed_week_no_false_incomplete_warning(self):
        result = {
            "granularity": "week",
            "series": [
                {"period": "2026-06-15", "revenue": 100.0, "orders": 10, "units": 50},
            ],
            "date_range": {"start": "2026-06-15", "end": "2026-06-21"},
            "query_date_range": {"start": "2026-06-15", "end": "2026-06-21"},
            "limitations": [],
        }
        out = apply_sales_over_time_period_policy(result)
        self.assertEqual(len(out["series"]), 1)
        self.assertIn("completed_week_label", out)
        self.assertNotIn("analysis_note", out)
        self.assertFalse(any("pågående" in l for l in out.get("limitations", [])))
        self.assertEqual(out.get("weekly_comparison_available"), False)
        self.assertIn("jämförbar veckodata", out.get("comparison_note", ""))

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
        series = [{"period": "2026-06-15", "revenue": 1}]
        self.assertEqual(
            series_date_range(series, "week"),
            {"start": "2026-06-15", "end": "2026-06-21"},
        )

    def test_named_calendar_month_with_year(self):
        out = resolve_period_range(
            "bara i månad mars 2026",
            reference=self.REF,
            data_min=self.DATA_MIN,
            data_max=self.DATA_MAX,
        )
        self.assertEqual(out["start_date"], "2026-03-01")
        self.assertEqual(out["end_date"], "2026-03-31")
        self.assertEqual(out.get("period_kind"), "calendar_month")

    def test_multiple_named_months_do_not_resolve_to_one(self):
        out = resolve_period_range(
            "mars 2026 och april 2026",
            reference=self.REF,
            data_min=self.DATA_MIN,
            data_max=self.DATA_MAX,
        )
        self.assertEqual(out, {})


if __name__ == "__main__":
    unittest.main()
