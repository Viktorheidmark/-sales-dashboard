"""Unit tests for deterministic chat guardrails."""

import unittest

from app.services.guardrails import classify


class GuardrailTests(unittest.TestCase):
    def test_inventory_question_uses_natural_swedish_copy(self):
        result = classify("Hur mycket lager har vi kvar?")
        self.assertEqual(result.classification, "insufficient_data")
        self.assertFalse(result.should_call_llm)
        self.assertIn("lagerdata", result.answer.lower())
        self.assertIn("säljer snabbast", result.answer)
        self.assertNotIn("verktyg", result.answer.lower())
        self.assertNotIn("mcp", result.answer.lower())

    def test_greeting_is_conversational(self):
        result = classify("hej")
        self.assertEqual(result.classification, "conversational")
        self.assertIn("Vad vill du analysera", result.answer)

    def test_thanks_is_conversational(self):
        result = classify("tack")
        self.assertEqual(result.classification, "conversational")
        self.assertIn("Vad vill du titta", result.answer)

    def test_capability_question_is_conversational(self):
        result = classify("vad kan du hjälpa mig med?")
        self.assertEqual(result.classification, "conversational")
        self.assertIn("försäljning", result.answer.lower())


if __name__ == "__main__":
    unittest.main()
