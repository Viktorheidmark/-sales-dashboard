"""Unit tests for response guidance helpers."""

import unittest

from app.services.response_guidance import (
    claims_unsupported_strong_decline,
    is_sustained_revenue_decline,
    sanitize_trend_wording,
)


class ResponseGuidanceTests(unittest.TestCase):
    def test_sustained_decline_requires_clear_tail(self):
        mixed = [
            {"revenue": 100},
            {"revenue": 120},
            {"revenue": 90},
            {"revenue": 110},
        ]
        self.assertFalse(is_sustained_revenue_decline(mixed))

        short_decline = [
            {"revenue": 100},
            {"revenue": 120},
            {"revenue": 90},
            {"revenue": 80},
        ]
        self.assertFalse(is_sustained_revenue_decline(short_decline))

        sustained = [
            {"revenue": 100},
            {"revenue": 120},
            {"revenue": 110},
            {"revenue": 90},
            {"revenue": 80},
            {"revenue": 70},
        ]
        self.assertTrue(is_sustained_revenue_decline(sustained))

    def test_claims_unsupported_strong_decline_on_mixed_series(self):
        answer = "Coca-Cola Europacific Partners Sverige har en nedåtgående trend under perioden."
        raw = [("get_sales_over_time", {"series": [
            {"revenue": 100}, {"revenue": 120}, {"revenue": 90}, {"revenue": 110},
        ]})]
        self.assertTrue(claims_unsupported_strong_decline(answer, raw))

    def test_allows_strong_decline_when_sustained(self):
        answer = "Coca-Cola Europacific Partners Sverige visar en nedåtgående trend."
        raw = [("get_sales_over_time", {"series": [
            {"revenue": 100}, {"revenue": 120}, {"revenue": 110},
            {"revenue": 90}, {"revenue": 80}, {"revenue": 70},
        ]})]
        self.assertFalse(claims_unsupported_strong_decline(answer, raw))

    def test_sanitize_trend_wording_softens_short_series(self):
        answer = "Försäljningen för Coca-Cola Europacific Partners Sverige visade en nedåtgående trend under perioden 25 maj–14 juni 2026."
        raw = [("get_sales_over_time", {"series": [
            {"revenue": 49}, {"revenue": 40}, {"revenue": 34},
        ]})]
        cleaned = sanitize_trend_wording(answer, raw)
        self.assertNotIn("nedåtgående trend", cleaned.lower())
        self.assertIn("varierade under perioden", cleaned.lower())
        self.assertNotIn("varierade under perioden under perioden", cleaned.lower())

    def test_soft_trend_phrase_for_lower_tail(self):
        series = [{"revenue": 49}, {"revenue": 40}, {"revenue": 34}]
        from app.services.response_guidance import _soft_trend_phrase
        self.assertIn("lägre", _soft_trend_phrase(series))


if __name__ == "__main__":
    unittest.main()
