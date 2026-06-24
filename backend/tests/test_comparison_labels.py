"""Tests for deterministic comparison and period labels."""

import unittest

from app.services.comparison_labels import (
    analyzed_period_label,
    build_comparison_context_block,
    comparison_metadata,
    kpi_comparison_label,
    market_share_period_label,
    revenue_drivers_comparison_label,
    weekly_sales_comparison_label,
)
from app.services.follow_up_builder import build_contextual_follow_ups
from app.services.response_guidance import (
    has_generic_recommendation,
    has_vague_comparison,
    sanitize_generic_recommendations,
    sanitize_vague_comparisons,
)


class ComparisonLabelTests(unittest.TestCase):
    def test_ytd_kpi_comparison_label_uses_prior_year_same_period(self):
        kpi = {
            "comparison_kind": "year_over_year",
            "date_range": {"start": "2026-01-01", "end": "2026-06-22"},
            "prev_date_range": {"start": "2025-01-01", "end": "2025-06-22"},
        }
        label = kpi_comparison_label(kpi)
        self.assertIn("jämfört med samma period föregående år", label)
        self.assertIn("1 januari–22 juni 2025", label)
        self.assertNotIn("föregående 173 dagarna", label)
        self.assertNotIn("11 juli", label)

    def test_30_day_revenue_drivers_comparison(self):
        drivers = {
            "comparison_days": 30,
            "prior_period": {"start": "2026-04-24", "end": "2026-05-23"},
        }
        label = revenue_drivers_comparison_label(drivers)
        self.assertIn("jämfört med föregående 30 dagarna", label)
        self.assertIn("24 april", label)

    def test_weekly_comparison_label(self):
        self.assertEqual(weekly_sales_comparison_label(), "jämfört med föregående avslutade vecka")

    def test_market_share_period_label_90_days(self):
        ms = {
            "category_name": "Läsk",
            "date_range": {"start": "2026-03-26", "end": "2026-06-23"},
        }
        label = market_share_period_label(ms)
        self.assertIn("Läsk", label)
        self.assertIn("90 dagarna", label)

    def test_market_share_metadata_includes_date_range(self):
        ms = {
            "category_name": "Läsk",
            "date_range": {"start": "2026-03-26", "end": "2026-06-23"},
        }
        meta = comparison_metadata([("get_market_share", ms)])
        self.assertIn("market_share_period_label", meta)
        self.assertEqual(meta["analyzed_date_range"]["start"], "2026-03-26")

    def test_comparison_context_block_for_ytd_overview(self):
        kpi = {
            "comparison_kind": "year_over_year",
            "date_range": {"start": "2026-01-01", "end": "2026-06-22"},
            "prev_date_range": {"start": "2025-01-01", "end": "2025-06-22"},
        }
        block = build_comparison_context_block([
            ("get_supplier_kpis", kpi),
            ("get_sales_over_time", {"date_range": kpi["date_range"], "series": []}),
        ])
        self.assertIn("OBLIGATORISK JÄMFÖRELSETEXT", block)
        self.assertIn("samma period föregående år", block)
        self.assertIn("1 januari–22 juni 2025", block)

    def test_ytd_overview_follow_ups_preserve_context(self):
        kpi = {"date_range": {"start": "2026-01-01", "end": "2026-06-22"}}
        actions = build_contextual_follow_ups(
            [
                ("get_supplier_kpis", kpi),
                ("get_sales_over_time", {"date_range": kpi["date_range"], "series": []}),
            ],
            question="Hur ser försäljningen ut i år?",
        )
        labels = [a["label"] for a in actions]
        self.assertIn("Visa produkter som drev utvecklingen", labels)
        self.assertIn("Jämför med samma period förra året", labels)
        self.assertTrue(any("i år" in a["message"] for a in actions))

    def test_market_share_follow_ups(self):
        ms = {
            "category_name": "Läsk",
            "date_range": {"start": "2026-03-26", "end": "2026-06-23"},
        }
        actions = build_contextual_follow_ups([("get_market_share", ms)])
        labels = [a["label"] for a in actions]
        self.assertIn("Visa våra starkaste produkter inom Läsk", labels)
        self.assertIn("Jämför med föregående 90 dagar", labels)

    def test_sanitize_vague_comparison(self):
        kpi = {
            "comparison_kind": "year_over_year",
            "date_range": {"start": "2026-01-01", "end": "2026-06-22"},
            "prev_date_range": {"start": "2025-01-01", "end": "2025-06-22"},
        }
        answer = "Omsättningen är högre jämfört med föregående period."
        cleaned = sanitize_vague_comparisons(answer, [("get_supplier_kpis", kpi)])
        self.assertNotIn("föregående period", cleaned.lower())
        self.assertIn("samma period föregående år", cleaned)

    def test_generic_recommendation_blocked(self):
        answer = (
            "Försäljningen ökade. "
            "För att fortsätta denna positiva utveckling kan det vara fördelaktigt att analysera produkterna."
        )
        self.assertTrue(has_generic_recommendation(answer))
        cleaned = sanitize_generic_recommendations(answer)
        self.assertNotIn("fördelaktigt", cleaned.lower())
        self.assertTrue(has_vague_comparison("Lägre än jämfört med tidigare."))


if __name__ == "__main__":
    unittest.main()
