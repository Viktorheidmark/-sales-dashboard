import unittest

from app.services.response_guidance import (
    executive_writing_rules,
    has_unsupported_recommendation,
    misnames_product,
    synthesis_blueprint,
    synthesis_suffix,
)


class ResponseGuidanceTests(unittest.TestCase):
    def test_executive_rules_forbid_ai_phrases(self):
        rules = executive_writing_rules("Arla Sverige")
        self.assertIn("dominerar marknaden", rules)
        self.assertIn("representeras av en aktör", rules)
        self.assertIn("ALDRIG leverantörsnamnet framför produktnamnet", rules)
        self.assertNotIn("Arla Sverige Iced Coffee Latte är största risken", rules)

    def test_market_share_blueprint(self):
        blueprint = synthesis_blueprint("Vad är vår marknadsandel i Mejeri?", ["get_market_share"])
        self.assertIn("Övriga aktörer", blueprint)
        self.assertIn("en aktör", blueprint)

    def test_trend_blueprint_skips_body_period_note(self):
        blueprint = synthesis_blueprint(
            "Hur har försäljningen utvecklats de senaste 90 dagarna?",
            ["get_sales_over_time"],
            "Arla Sverige",
        )
        self.assertIn("diagrammet", blueprint)

    def test_focus_blueprint_one_followup(self):
        blueprint = synthesis_blueprint("Vad borde vi fokusera på nästa period?", [])
        self.assertIn("högst ETT", blueprint)
        self.assertIn("Jämför produkten mellan regioner", blueprint)

    def test_synthesis_suffix_includes_question_type(self):
        suffix = synthesis_suffix(
            "Arla Sverige",
            "Vilka produkter säljer bäst i Stockholm?",
            ["get_top_products"],
        )
        self.assertIn("Topprodukter", suffix)

    def test_detects_unsupported_recommendation(self):
        self.assertTrue(has_unsupported_recommendation("Överväg att analysera försäljningen."))

    def test_detects_misnamed_product(self):
        self.assertTrue(misnames_product("Arla Sverige Iced Coffee Latte minskade.", "Arla Sverige"))
        self.assertFalse(misnames_product("Arla Iced Coffee Latte minskade.", "Arla Sverige"))


if __name__ == "__main__":
    unittest.main()
