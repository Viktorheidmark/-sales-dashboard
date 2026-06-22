"""
Unit tests for deterministic intent routing (no API / LLM required).
Run: python -m unittest tests.test_intent_router
"""

import unittest

from app.services.intent_router import (
    default_category_for_supplier,
    extract_category,
    extract_region,
    plan_forced_tools,
)


class IntentRouterTests(unittest.TestCase):
    def test_default_category_arla(self):
        self.assertEqual(default_category_for_supplier("Arla Sverige"), "Mejeri")

    def test_brand_vs_competitors_forces_market_share_mejeri(self):
        plans = plan_forced_tools(
            "Hur går det för vårt märke jämfört med konkurrenterna?",
            "Arla Sverige",
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_market_share")
        self.assertEqual(plans[0].args["category_name"], "Mejeri")

    def test_explicit_mejeri_market_share(self):
        plans = plan_forced_tools(
            "Vad är vår marknadsandel i Mejeri?",
            "Arla Sverige",
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_market_share")
        self.assertEqual(plans[0].args["category_name"], "Mejeri")

    def test_top_products_stockholm(self):
        plans = plan_forced_tools(
            "Vilka produkter säljer bäst i Stockholm?",
            "Arla Sverige",
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_top_products")
        self.assertEqual(plans[0].args["region"], "Stockholm")

    def test_extract_category_and_region(self):
        self.assertEqual(extract_category("Marknadsandel i Dryck"), "Dryck")
        self.assertEqual(extract_region("försäljning i Göteborg"), "Göteborg")


if __name__ == "__main__":
    unittest.main()
