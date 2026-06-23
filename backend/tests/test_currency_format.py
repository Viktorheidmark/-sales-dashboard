import unittest

from app.services.currency_format import (
    build_currency_reference_block,
    format_compact_sek,
    sanitize_answer_currency,
)


class CurrencyFormatTests(unittest.TestCase):
    def test_format_examples(self):
        self.assertEqual(format_compact_sek(75619), "75,6 tkr")
        self.assertEqual(format_compact_sek(52358.6), "52,4 tkr")
        self.assertEqual(format_compact_sek(971.1), "971 kr")
        self.assertEqual(format_compact_sek(1200000), "1,2 mkr")

    def test_never_mkr_below_one_million_sek(self):
        self.assertTrue(format_compact_sek(999_999).endswith("tkr"))
        self.assertTrue(format_compact_sek(1_000_000).endswith("mkr"))

    def test_sanitize_mislabeled_mkr(self):
        tool_results = [
            ("get_market_share", {"category_total_revenue": 75619, "supplier_revenue": 52358.6}),
        ]
        answer = "Total omsättning i kategorin är 75,6 mkr."
        fixed = sanitize_answer_currency(answer, tool_results)
        self.assertIn("75,6 tkr", fixed)
        self.assertNotIn("75,6 mkr", fixed)

    def test_currency_reference_block(self):
        block = build_currency_reference_block([
            ("get_top_products", {"products": [{"product_name": "A", "revenue": 75619}]}),
        ])
        self.assertIn("75,6 tkr", block)
        self.assertIn("VALUTAREFERENS", block)


if __name__ == "__main__":
    unittest.main()
