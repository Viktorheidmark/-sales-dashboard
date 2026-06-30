"""Tests for deterministic comparison and period labels."""

import unittest

from app.services.comparison_labels import (
    analyzed_period_label,
    build_comparison_context_block,
    comparison_metadata,
    comparison_needs_dimension_clarification,
    comparison_needs_period_clarification,
    kpi_comparison_is_meaningful,
    kpi_comparison_label,
    market_share_period_label,
    question_requests_comparison,
    revenue_drivers_comparison_label,
    weekly_sales_comparison_label,
)
from app.services.period_labels import decline_comparison_period_label
from app.services.follow_up_builder import build_contextual_follow_ups
from app.services.response_guidance import (
    has_generic_recommendation,
    has_vague_comparison,
    sanitize_generic_recommendations,
    sanitize_vague_comparisons,
    strip_unrequested_comparison,
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
        self.assertIn("Hittills i år", label)
        self.assertNotIn("föregående 173 dagarna", label)
        self.assertNotIn("11 juli", label)

    def test_30_day_revenue_drivers_comparison(self):
        drivers = {
            "comparison_days": 30,
            "prior_period": {"start": "2026-04-24", "end": "2026-05-23"},
        }
        label = revenue_drivers_comparison_label(drivers)
        self.assertIn("Senaste 30 dagarna", label)
        self.assertIn("jämfört med föregående 30 dagar", label)
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

    def test_comparison_context_block_for_ytd_overview_with_explicit_compare(self):
        kpi = {
            "comparison_kind": "year_over_year",
            "date_range": {"start": "2026-01-01", "end": "2026-06-22"},
            "prev_date_range": {"start": "2025-01-01", "end": "2025-06-22"},
            "total_revenue": 5_000_000.0,
            "prev_total_revenue": 4_500_000.0,
            "prev_total_orders": 1000,
        }
        block = build_comparison_context_block([
            ("get_supplier_kpis", kpi),
            ("get_sales_over_time", {"date_range": kpi["date_range"], "series": []}),
        ], question="Hur ser försäljningen ut i år jämfört med förra året?")
        self.assertIn("OBLIGATORISK JÄMFÖRELSETEXT", block)
        self.assertIn("samma period föregående år", block)

    def test_status_question_omits_mandatory_kpi_comparison(self):
        kpi = {
            "comparison_kind": "prior_equal_length",
            "date_range": {"start": "2024-06-23", "end": "2026-06-22"},
            "prev_date_range": {"start": "2022-06-24", "end": "2024-06-22"},
            "total_revenue": 19_100_000.0,
            "prev_total_revenue": 123_500.0,
            "prev_total_orders": 5,
        }
        block = build_comparison_context_block([
            ("get_supplier_kpis", kpi),
            ("get_sales_over_time", {"date_range": kpi["date_range"], "series": []}),
        ], question="hur ser försäljningen ut?")
        self.assertNotIn("OBLIGATORISK JÄMFÖRELSETEXT", block)
        self.assertIn("Nämn INTE procentuell förändring", block)

    def test_kpi_comparison_not_meaningful_for_sparse_prior(self):
        kpi = {
            "total_revenue": 19_100_000.0,
            "prev_total_revenue": 123_500.0,
            "prev_total_orders": 5,
        }
        self.assertFalse(kpi_comparison_is_meaningful(kpi))

    def test_vague_compare_intent_needs_clarification(self):
        self.assertTrue(comparison_needs_dimension_clarification("Är försäljningen bättre nu?"))
        self.assertFalse(comparison_needs_period_clarification("Är försäljningen bättre nu?"))
        self.assertFalse(comparison_needs_period_clarification("hur ser försäljningen ut?"))
        self.assertTrue(
            comparison_needs_period_clarification(
                "Hur ser försäljningen ut jämfört med föregående period?"
            )
        )
        self.assertTrue(
            comparison_needs_period_clarification(
                "Jämför försäljningen med förra perioden"
            )
        )
        self.assertTrue(
            comparison_needs_period_clarification(
                "Har försäljningen ökat eller minskat?"
            )
        )
        self.assertFalse(
            comparison_needs_period_clarification(
                "Jämför senaste 30 dagarna mot föregående 30 dagar"
            )
        )
        self.assertFalse(
            comparison_needs_period_clarification(
                "Vilken produkt har tappat mest senaste 30 dagarna?"
            )
        )

    def test_strip_unrequested_comparison(self):
        answer = (
            "Ni har haft en omsättning på 19 mkr. "
            "Jämfört med föregående 730 dagarna har omsättningen ökat markant från 123,5 tkr."
        )
        cleaned = strip_unrequested_comparison(answer, "hur ser försäljningen ut?")
        self.assertNotIn("Jämfört med föregående", cleaned)
        self.assertIn("19 mkr", cleaned)

    def test_question_requests_comparison(self):
        self.assertTrue(question_requests_comparison("jämfört med föregående period"))
        self.assertFalse(question_requests_comparison("hur går försäljningen?"))

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
        self.assertEqual(len(actions), 3)
        self.assertIn("Visa vilka produkter som driver utvecklingen", labels)
        self.assertIn("Visa utveckling per vecka", labels)
        self.assertIn("Visa utveckling per region", labels)
        weekly = next(a for a in actions if a["label"] == "Visa utveckling per vecka")
        self.assertEqual(weekly.get("action"), "weekly_trend")
        self.assertIn("start_date", weekly.get("context", {}))
        self.assertTrue(any("i år" in a["message"] for a in actions))

    def test_decline_comparison_period_label(self):
        label = decline_comparison_period_label({
            "comparison_days": 365,
            "prior_period": {"start": "2024-06-23", "end": "2025-06-23"},
            "latest_period": {"start": "2025-06-24", "end": "2026-06-23"},
        })
        self.assertIn("Senaste 365 dagarna", label)
        self.assertIn("jämfört med", label)
        self.assertIn("föregående 365 dagar", label)
        self.assertIn("2024", label)
        self.assertIn("2026", label)

    def test_decline_empty_products_synthesis_instruction(self):
        block = build_comparison_context_block(
            [("get_declining_products", {"products": [], "comparison_days": 30})],
            "Vilken produkt har tappat mest?",
        )
        self.assertIn("INGA PRODUKTER I NEDGÅNG", block)
        ms = {
            "category_name": "Läsk",
            "date_range": {"start": "2026-03-26", "end": "2026-06-23"},
        }
        actions = build_contextual_follow_ups([("get_market_share", ms)])
        labels = [a["label"] for a in actions]
        self.assertEqual(len(actions), 3)
        self.assertIn("Visa våra starkaste produkter inom Läsk", labels)
        self.assertTrue(any(label.startswith("Visa marknadsandel") for label in labels))
        self.assertIn("Visa försäljning per region", labels)

    def test_sanitize_vague_comparison(self):
        kpi = {
            "comparison_kind": "year_over_year",
            "date_range": {"start": "2026-01-01", "end": "2026-06-22"},
            "prev_date_range": {"start": "2025-01-01", "end": "2025-06-22"},
            "total_revenue": 5_000_000.0,
            "prev_total_revenue": 4_500_000.0,
            "prev_total_orders": 1000,
        }
        answer = "Omsättningen är högre jämfört med föregående period."
        cleaned = sanitize_vague_comparisons(
            answer,
            [("get_supplier_kpis", kpi)],
            question="Hur ser försäljningen ut jämfört med förra året?",
        )
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
