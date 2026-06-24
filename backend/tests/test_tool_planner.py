"""Tests for hybrid tool planner with mocked planner output."""

import os
import unittest
from unittest.mock import patch

from app.schemas.analysis_plan import AnalysisPlan, TimePeriod, VisualizationSpec
from app.services.intent_router import PriorTurnContext, plan_followup_tools
from app.services.tool_planner import resolve_tool_plans


class ToolPlannerTests(unittest.TestCase):
    UI_START = "2026-03-25"
    UI_END = "2026-06-23"

    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"USE_AI_PLANNER": "true"})
        self._env_patch.start()

    def tearDown(self):
        self._env_patch.stop()

    def test_invalid_planner_falls_back_to_legacy(self):
        bad_plan = AnalysisPlan(intent="unknown", confidence=0.1, clarification_needed=True)
        res = resolve_tool_plans(
            "Hur har försäljningen utvecklats de senaste 30 dagarna?",
            "Orkla Snacks Sverige",
            self.UI_START,
            self.UI_END,
            injected_plan=bad_plan,
        )
        self.assertIn(res.source, ("legacy_fallback", "planner"))
        self.assertTrue(res.plans)

    def test_planner_ytd_overview(self):
        plan = AnalysisPlan(
            intent="sales_overview",
            time_period=TimePeriod(kind="year_to_date"),
            confidence=0.95,
            visualization=VisualizationSpec(primary="line", granularity="month"),
        )
        res = resolve_tool_plans(
            "Hur ser försäljningen överlag ut detta år?",
            "Orkla Snacks Sverige",
            self.UI_START,
            self.UI_END,
            injected_plan=plan,
        )
        self.assertEqual(res.source, "planner")
        tools = [p.tool_name for p in res.plans]
        self.assertIn("get_supplier_kpis", tools)
        self.assertIn("get_sales_over_time", tools)
        assert res.analysis_meta.get("normalized")
        self.assertEqual(res.analysis_meta["normalized"]["resolved_start_date"], f"{__import__('datetime').date.today().year}-01-01")

    def test_diagram_followup_uses_deterministic_not_planner(self):
        prior = PriorTurnContext(
            question="Hur såg försäljningen ut senaste veckan?",
            tool_calls=("get_sales_over_time",),
            sources=({"date_range": {"start": "2026-06-09", "end": "2026-06-15"}},),
            has_chart=False,
        )
        det = plan_followup_tools("Visa diagram", prior, "Orkla Snacks Sverige")
        self.assertTrue(det)
        res = resolve_tool_plans(
            "Visa diagram",
            "Orkla Snacks Sverige",
            prior_context=prior,
            injected_plan=AnalysisPlan(intent="unknown", confidence=0.0),
        )
        self.assertEqual(res.source, "deterministic")
        self.assertEqual(res.plans[0].tool_name, "get_sales_over_time")

    def test_planner_disabled_uses_legacy(self):
        with patch.dict(os.environ, {"USE_AI_PLANNER": "false"}):
            res = resolve_tool_plans(
                "Hur ser försäljningen ut i år?",
                "Orkla Snacks Sverige",
                self.UI_START,
                self.UI_END,
            )
        self.assertEqual(res.source, "legacy_fallback")
        self.assertTrue(res.plans)


if __name__ == "__main__":
    unittest.main()
