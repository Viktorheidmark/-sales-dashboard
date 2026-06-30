"""Tests for customer-safe chat response sanitization and non-stream serialization."""

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import app
from app.schemas.chat import ChatResponse
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
        "supplier_id": "supplier-1",
        "generated_at": "2026-06-28T12:00:00+00:00",
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


class ChatResponseSchemaTests(unittest.TestCase):
    @patch("app.services.chat.analytics_debug_trace_enabled", return_value=False)
    def test_prepared_payload_validates_as_chat_response(self, _mock):
        out = _prepare_client_response(_sample_payload())
        response = ChatResponse(**out)
        self.assertEqual(len(response.sources), 1)
        self.assertIsNotNone(response.sources[0].date_range)
        self.assertEqual(response.sources[0].date_range.start, "2024-06-01")
        self.assertNotIn("tool", out["sources"][0])
        self.assertNotIn("supplier_id", out["sources"][0])

    @patch("app.services.chat.analytics_debug_trace_enabled", return_value=True)
    def test_debug_diagnostics_validate_on_chat_response(self, _mock):
        out = _prepare_client_response(_sample_payload())
        response = ChatResponse(**out)
        self.assertIsNotNone(response.debug_diagnostics)
        assert response.debug_diagnostics is not None
        self.assertEqual(response.debug_diagnostics.sources[0]["tool"], "get_supplier_kpis")
        self.assertEqual(response.sources[0].date_range.start, "2024-06-01")


def _prepared_chat_result() -> dict:
    return {
        "answer": "Omsättningen uppgick till 1,2 mkr.",
        "tool_calls": ["get_supplier_kpis", "get_sales_over_time"],
        "sources": [
            {"date_range": {"start": "2024-06-01", "end": "2026-06-27"}},
            {"date_range": {"start": "2024-06-01", "end": "2026-05-31"}},
        ],
        "chart": None,
        "charts": [],
        "deep_dive": None,
        "follow_up_actions": [],
        "analysis_context": None,
        "limitations": [],
        "supplier_id": "d49b6ba8-5afb-4136-b1bd-eeeadd32c1b0",
        "generated_at": "2026-06-30T12:00:00+00:00",
    }


class NonStreamChatRouterTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_current_user] = lambda: {
            "supplier_id": "d49b6ba8-5afb-4136-b1bd-eeeadd32c1b0",
            "supplier_name": "Coca-Cola Europacific Partners Sverige",
            "email": "cocacola@demo.solvigo",
        }
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    @patch("app.routers.chat.run_chat", new_callable=AsyncMock)
    def test_non_stream_chat_returns_200_with_customer_safe_sources(self, mock_run_chat):
        mock_run_chat.return_value = _prepared_chat_result()
        r = self.client.post("/api/chat", json={"message": "hur går försäljningen?"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("answer", body)
        self.assertEqual(body["tool_calls"], ["get_supplier_kpis", "get_sales_over_time"])
        self.assertEqual(len(body["sources"]), 2)
        for src in body["sources"]:
            self.assertIn("date_range", src)
            self.assertNotIn("tool", src)
            self.assertNotIn("source", src)
            self.assertNotIn("supplier_id", src)
            self.assertNotIn("generated_at", src)
            self.assertNotIn("row_count", src)


if __name__ == "__main__":
    unittest.main()
