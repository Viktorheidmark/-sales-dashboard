"""Tests for customer-safe chat response sanitization."""

import unittest
from unittest.mock import patch

from app.services.chat import _prepare_client_response


def _full_source() -> dict:
    return {
        "tool": "get_supplier_kpis",
        "source": "MCP:get_supplier_kpis",
        "supplier_id": "supplier-1",
        "generated_at": "2026-06-28T12:00:00+00:00",
        "row_count": 1284,
        "date_range": {"start": "2024-06-01", "end": "2026-06-27"},
    }


def _sample_payload() -> dict:
    return {
        "answer": "Analys",
        "tool_calls": ["get_supplier_kpis"],
        "sources": [_full_source()],
        "limitations": ["Ofullständig månad exkluderad"],
        "analysis_meta": {"source": "planner", "intent": "period_comparison"},
    }


class ChatClientPayloadTests(unittest.TestCase):
    @patch("app.services.chat.analytics_debug_trace_enabled", return_value=False)
    def test_debug_off_strips_technical_source_fields(self, _mock):
        out = _prepare_client_response(_sample_payload())
        self.assertNotIn("debug_diagnostics", out)
        self.assertNotIn("analysis_meta", out)
        self.assertEqual(len(out["sources"]), 1)
        src = out["sources"][0]
        self.assertEqual(src, {"date_range": {"start": "2024-06-01", "end": "2026-06-27"}})
        self.assertNotIn("tool", src)
        self.assertNotIn("source", src)
        self.assertNotIn("row_count", src)

    @patch("app.services.chat.analytics_debug_trace_enabled", return_value=False)
    def test_debug_off_preserves_tool_calls_for_client_logic(self, _mock):
        out = _prepare_client_response(_sample_payload())
        self.assertEqual(out["tool_calls"], ["get_supplier_kpis"])

    @patch("app.services.chat.analytics_debug_trace_enabled", return_value=True)
    def test_debug_on_attaches_developer_diagnostics(self, _mock):
        out = _prepare_client_response(_sample_payload())
        diag = out.get("debug_diagnostics")
        self.assertIsNotNone(diag)
        assert diag is not None
        self.assertEqual(diag["tool_calls"], ["get_supplier_kpis"])
        self.assertEqual(diag["sources"][0]["tool"], "get_supplier_kpis")
        self.assertEqual(diag["sources"][0]["row_count"], 1284)
        self.assertEqual(diag["analysis_meta"]["intent"], "period_comparison")
        # Customer-facing sources remain minimal
        self.assertEqual(out["sources"][0], {"date_range": {"start": "2024-06-01", "end": "2026-06-27"}})

    @patch("app.services.chat.analytics_debug_trace_enabled", return_value=True)
    def test_debug_on_includes_orchestration_trace_in_diagnostics(self, _mock):
        payload = _sample_payload()
        payload["analysis_meta"] = {"orchestration_trace": {"stage": "verifier", "result": "ok"}}
        out = _prepare_client_response(payload)
        trace = out["debug_diagnostics"]["analysis_meta"]["orchestration_trace"]
        self.assertEqual(trace["stage"], "verifier")


if __name__ == "__main__":
    unittest.main()
