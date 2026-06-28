"""
Unit + integration tests for the canonical analytics pipeline (explicit
comparison capability): planner, validator, executor, verifier, chart builder,
responder, and the orchestrator end-to-end.
"""

import asyncio
import unittest
from datetime import date, timedelta

from app.analytics import chart_builder, planner, responder, verifier
from app.analytics.executor import execute_plan
from app.analytics.orchestrator import comparison_precheck, orchestrate_comparison
from app.analytics.schemas import AnalysisPlan, AnalysisResult, ComparisonSpec, DateRange
from app.analytics.validator import validate_plan
from app.services.period_utils import default_data_bounds, latest_completed_date


def _run(coro):
    return asyncio.run(coro)


class PlannerTests(unittest.TestCase):
    def test_explicit_month_pair(self):
        plan = planner.plan_comparison("Jämför försäljningen mellan mars 2026 och april 2026")
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.intent, "period_comparison")
        self.assertEqual(plan.comparison.comparison_type, "month_over_month")
        self.assertEqual(plan.comparison.period_a.start, date(2026, 3, 1))
        self.assertEqual(plan.comparison.period_a.end, date(2026, 3, 31))
        self.assertEqual(plan.comparison.period_b.start, date(2026, 4, 1))
        self.assertEqual(plan.comparison.period_b.end, date(2026, 4, 30))
        self.assertEqual(plan.comparison.source, "explicit_free_text")
        self.assertFalse(plan.needs_clarification)

    def test_month_pair_without_year_uses_reference_year(self):
        plan = planner.plan_comparison("jämför mars och april")
        self.assertIsNotNone(plan)
        assert plan is not None
        ref_year = latest_completed_date().year
        self.assertEqual(plan.comparison.period_a.start.year, ref_year)
        self.assertEqual(plan.comparison.period_b.start.month, 4)

    def test_rolling_pair(self):
        plan = planner.plan_comparison("Jämför senaste 30 dagarna mot föregående 30 dagar")
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.comparison.comparison_type, "rolling")
        end_b = latest_completed_date()
        self.assertEqual(plan.comparison.period_b.end, end_b)
        self.assertEqual(plan.comparison.period_b.start, end_b - timedelta(days=29))
        self.assertEqual(plan.comparison.period_a.end, end_b - timedelta(days=30))

    def test_ytd_vs_prior_year(self):
        plan = planner.plan_comparison("i år jämfört med förra året")
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.comparison.comparison_type, "year_over_year")
        end = latest_completed_date()
        self.assertEqual(plan.comparison.period_b.start, date(end.year, 1, 1))
        self.assertEqual(plan.comparison.period_a.start, date(end.year - 1, 1, 1))

    def test_ytd_chart_labels_use_exact_equivalent_ranges(self):
        """Regression: YTD YoY chart labels must show exact equivalent ranges, not
        vague 'helåret' / 'hittills år' wording."""
        from app.services.period_utils import format_date_range_sv
        from app.analytics.labels import readable_range

        plan = planner.plan_comparison("Jämför i år med förra året")
        self.assertIsNotNone(plan)
        assert plan is not None
        spec = plan.comparison
        end = latest_completed_date()

        expected_a = format_date_range_sv(
            spec.period_a.start.isoformat(), spec.period_a.end.isoformat()
        )
        expected_b = format_date_range_sv(
            spec.period_b.start.isoformat(), spec.period_b.end.isoformat()
        )

        a_label = readable_range(spec.period_a)
        b_label = readable_range(spec.period_b)
        self.assertEqual(a_label, expected_a)
        self.assertEqual(b_label, expected_b)
        for label in (a_label, b_label):
            self.assertNotIn("helåret", label.lower())
            self.assertNotIn("hittills", label.lower())

        # Chart payload must carry the same readable labels on the axis.
        mock_result = AnalysisResult(
            plan_id="ytd-test",
            tenant_id="s1",
            supplier_id="s1",
            resolved_plan=plan,
            primary_period=spec.period_b,
            comparison_period=spec.period_a,
            kpis={
                "metric": "revenue",
                "current": {"revenue": 100.0},
                "prior": {"revenue": 90.0},
            },
            source_tools=["get_supplier_kpis"],
        )
        chart = chart_builder.build_chart_payload(mock_result)
        assert chart is not None
        axis_labels = [row["label"] for row in chart["data"]]
        self.assertEqual(axis_labels[0], expected_a)
        self.assertEqual(axis_labels[1], expected_b)
        self.assertEqual(chart["period_a_label"], expected_a)
        self.assertEqual(chart["period_b_label"], expected_b)
        self.assertIn(expected_b, chart["period_note"])
        self.assertIn(expected_a, chart["period_note"])
        self.assertIn(str(end.year), expected_b)
        self.assertIn(str(end.year - 1), expected_a)

    def test_vague_comparison_opens_composer(self):
        plan = planner.plan_comparison("Jämför försäljningen med förra perioden")
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.intent, "clarification")
        self.assertTrue(plan.needs_clarification)
        self.assertEqual(plan.clarification_type, "comparison_dates")

    def test_non_comparison_defers(self):
        self.assertIsNone(planner.plan_comparison("Hur ser försäljningen ut senaste 30 dagarna?"))

    def test_composer_action_builds_exact_plan(self):
        action = {
            "action": "compare_periods",
            "context": {
                "period_a_start": "2026-03-01", "period_a_end": "2026-03-31",
                "period_b_start": "2026-04-01", "period_b_end": "2026-04-30",
                "comparison_mode": "custom",
            },
        }
        plan = planner.plan_comparison("Jämför perioder", follow_up_action=action)
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.comparison.source, "comparison_composer")
        self.assertEqual(plan.comparison.period_a.start, date(2026, 3, 1))


class ValidatorTests(unittest.TestCase):
    def _plan(self, pa, pb, ctype="month_over_month"):
        return AnalysisPlan(
            intent="period_comparison", metric="revenue",
            comparison=ComparisonSpec(period_a=pa, period_b=pb, comparison_type=ctype, source="explicit_free_text"),
            chart_intent="comparison_bar", output_sections=["comparison"],
            confidence=0.95, reasoning_summary="x",
        )

    def test_in_bounds_comparison_approved(self):
        plan = self._plan(
            DateRange(start=date(2026, 3, 1), end=date(2026, 3, 31)),
            DateRange(start=date(2026, 4, 1), end=date(2026, 4, 30)),
        )
        self.assertTrue(validate_plan(plan).approved)

    def test_out_of_bounds_period_clarifies(self):
        # A period far in the future, outside data bounds.
        plan = self._plan(
            DateRange(start=date(2099, 3, 1), end=date(2099, 3, 31)),
            DateRange(start=date(2099, 4, 1), end=date(2099, 4, 30)),
        )
        out = validate_plan(plan)
        self.assertFalse(out.approved)
        self.assertEqual(out.clarification_type, "comparison_dates")

    def test_clarification_plan_is_terminal(self):
        plan = planner.plan_comparison("Jämför försäljningen")
        out = validate_plan(plan)
        self.assertTrue(out.needs_clarification)


class ExecutorVerifierResponderTests(unittest.TestCase):
    def _plan(self):
        return planner.plan_comparison("Jämför mars 2026 och april 2026")

    async def _fake_runner(self, tool, args):
        # March = baseline (lower), April = current (higher).
        if args["start_date"] == "2026-04-01":
            return {"total_revenue": 877600.0, "total_orders": 120, "total_units": 5400, "average_order_value": 7313.0}
        return {"total_revenue": 754300.0, "total_orders": 110, "total_units": 5000, "average_order_value": 6857.0}

    def test_executor_preserves_exact_periods(self):
        plan = self._plan()
        result = _run(execute_plan(plan, tenant_id="t1", supplier_id="s1", tool_runner=self._fake_runner))
        self.assertEqual(result.primary_period.start, date(2026, 4, 1))
        self.assertEqual(result.comparison_period.start, date(2026, 3, 1))
        self.assertEqual(result.kpis["current"]["revenue"], 877600.0)
        self.assertEqual(result.kpis["prior"]["revenue"], 754300.0)
        self.assertAlmostEqual(result.kpis["delta"]["revenue_pct"], 16.3, places=1)

    def test_chart_and_verifier_pass(self):
        plan = self._plan()
        result = _run(execute_plan(plan, tenant_id="s1", supplier_id="s1", tool_runner=self._fake_runner))
        chart = chart_builder.build_chart_payload(result, tenant_theme={"supplier_name": "Estrella AB"})
        result.chart_data = chart
        self.assertEqual(chart["period_a"], {"start": "2026-03-01", "end": "2026-03-31", "label": "mars 2026"})
        self.assertEqual(chart["period_b"]["start"], "2026-04-01")
        verdict = verifier.verify(plan, result, chart, expected_supplier_id="s1", expected_tenant_id="s1")
        self.assertTrue(verdict.approved)
        self.assertTrue(verdict.verified_periods_match)
        self.assertTrue(verdict.verified_chart_match)

    def test_verifier_blocks_mismatched_chart_period(self):
        plan = self._plan()
        result = _run(execute_plan(plan, tenant_id="s1", supplier_id="s1", tool_runner=self._fake_runner))
        chart = chart_builder.build_chart_payload(result)
        # Tamper: simulate a hidden rolling window leaking into the chart.
        chart["period_a"] = {"start": "2025-06-01", "end": "2025-06-30"}
        verdict = verifier.verify(plan, result, chart, expected_supplier_id="s1", expected_tenant_id="s1")
        self.assertFalse(verdict.approved)
        self.assertEqual(verdict.severity, "blocking")
        self.assertFalse(verdict.verified_chart_match)

    def test_verifier_blocks_scope_mismatch(self):
        plan = self._plan()
        result = _run(execute_plan(plan, tenant_id="s1", supplier_id="s1", tool_runner=self._fake_runner))
        chart = chart_builder.build_chart_payload(result)
        verdict = verifier.verify(plan, result, chart, expected_supplier_id="OTHER", expected_tenant_id="s1")
        self.assertFalse(verdict.approved)
        self.assertFalse(verdict.verified_scope_match)

    def test_responder_uses_exact_ranges(self):
        plan = self._plan()
        result = _run(execute_plan(plan, tenant_id="s1", supplier_id="s1", tool_runner=self._fake_runner))
        answer = responder.render_answer(result)
        self.assertIn("1–30 april 2026", answer)
        self.assertIn("1–31 mars 2026", answer)
        self.assertNotIn("senaste", answer.lower())


class OrchestratorTests(unittest.TestCase):
    async def _runner(self, tool, args):
        if args["start_date"] == "2026-04-01":
            return {"total_revenue": 877600.0, "total_orders": 120, "total_units": 5400, "average_order_value": 7313.0}
        return {"total_revenue": 754300.0, "total_orders": 110, "total_units": 5000, "average_order_value": 6857.0}

    def test_end_to_end_explicit_comparison_answer(self):
        outcome = _run(orchestrate_comparison(
            "Jämför försäljningen mellan mars 2026 och april 2026",
            supplier_id="s1", supplier_name="Estrella AB", tool_runner=self._runner,
        ))
        self.assertEqual(outcome.kind, "answer")
        self.assertEqual(outcome.payload["response_kind"], "conversational")
        self.assertIn("1–30 april 2026", outcome.payload["answer"])
        self.assertEqual(outcome.payload["chart"]["intent"], "period_comparison")
        self.assertEqual(outcome.payload["chart"]["period_a"]["start"], "2026-03-01")
        self.assertEqual(outcome.trace["verifier_approved"], True)
        self.assertEqual(outcome.trace["result"], "answer")

    def test_response_contains_exactly_one_chart_payload(self):
        # Invariant: one analysis result → one primary chart, no duplicate in `charts`.
        outcome = _run(orchestrate_comparison(
            "Jämför försäljningen mellan mars 2026 och april 2026",
            supplier_id="s1", supplier_name="Estrella AB", tool_runner=self._runner,
        ))
        self.assertIsNotNone(outcome.payload["chart"])
        self.assertEqual(outcome.payload["charts"], [])

    def test_chart_labels_are_swedish_not_iso(self):
        # Composer custom dates have no human label → must format Swedish, never ISO.
        action = {
            "action": "compare_periods",
            "context": {
                "period_a_start": "2026-03-01", "period_a_end": "2026-03-31",
                "period_b_start": "2026-05-01", "period_b_end": "2026-05-22",
                "comparison_mode": "custom",
            },
        }
        outcome = _run(orchestrate_comparison(
            "Jämför perioder", supplier_id="s1", supplier_name="Estrella AB",
            tool_runner=self._runner, follow_up_action=action,
        ))
        chart = outcome.payload["chart"]
        labels = [row["label"] for row in chart["data"]]
        self.assertIn("1–22 maj 2026", labels)
        self.assertIn("1–31 mars 2026", labels)
        for label in labels:
            self.assertNotRegex(label, r"\d{4}-\d{2}-\d{2}")
        # Machine fields keep raw ISO for the verifier / dedup.
        self.assertEqual(chart["period_b"]["start"], "2026-05-01")

    def test_end_to_end_vague_opens_composer(self):
        outcome = _run(orchestrate_comparison(
            "Jämför försäljningen med förra perioden",
            supplier_id="s1", supplier_name="Estrella AB", tool_runner=self._runner,
        ))
        self.assertEqual(outcome.kind, "clarify_composer")
        self.assertEqual(outcome.trace["result"], "clarify_composer")

    def test_non_comparison_defers(self):
        outcome = _run(orchestrate_comparison(
            "Hur ser försäljningen ut senaste 30 dagarna?",
            supplier_id="s1", supplier_name="Estrella AB", tool_runner=self._runner,
        ))
        self.assertEqual(outcome.kind, "defer")

    def test_broad_overview_defers_without_running_tools(self):
        # "Hur har försäljningen gått?" must defer to legacy (which renders the
        # full-history line chart) — the precheck does this with no tool calls.
        calls = []

        async def tracking_runner(tool, args):
            calls.append(tool)
            return {}

        outcome = _run(orchestrate_comparison(
            "Hur har försäljningen gått?",
            supplier_id="s1", supplier_name="Estrella AB", tool_runner=tracking_runner,
        ))
        self.assertEqual(outcome.kind, "defer")
        self.assertEqual(calls, [])

    def test_precheck_is_mcp_free_for_defer_and_clarify(self):
        # Precheck must classify without any tool runner at all.
        defer, _ = comparison_precheck("Hur har försäljningen gått?", tenant_id="s1")
        self.assertEqual(defer.kind, "defer")

        clarify, _ = comparison_precheck("Jämför försäljningen med förra perioden", tenant_id="s1")
        self.assertEqual(clarify.kind, "clarify_composer")

        execute, plan = comparison_precheck(
            "Jämför försäljningen mellan mars 2026 och april 2026", tenant_id="s1"
        )
        self.assertEqual(execute.kind, "execute")
        self.assertIsNotNone(plan)

    def test_composer_action_end_to_end(self):
        action = {
            "action": "compare_periods",
            "context": {
                "period_a_start": "2026-03-01", "period_a_end": "2026-03-31",
                "period_b_start": "2026-04-01", "period_b_end": "2026-04-30",
                "comparison_mode": "custom",
            },
        }
        outcome = _run(orchestrate_comparison(
            "Jämför perioder", supplier_id="s1", supplier_name="Estrella AB",
            tool_runner=self._runner, follow_up_action=action,
        ))
        self.assertEqual(outcome.kind, "answer")
        self.assertEqual(outcome.payload["chart"]["period_b"]["end"], "2026-04-30")


if __name__ == "__main__":
    unittest.main()
