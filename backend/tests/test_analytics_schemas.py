"""Unit tests for the canonical analytics lifecycle schemas (Phase 1)."""

import unittest
from datetime import date

from pydantic import ValidationError

from app.analytics.schemas import (
    AnalysisPlan,
    AnalysisResult,
    ComparisonSpec,
    ConversationAnalysisContext,
    DateRange,
    VerificationResult,
)


def _march() -> DateRange:
    return DateRange(start=date(2026, 3, 1), end=date(2026, 3, 31), label="mars 2026")


def _april() -> DateRange:
    return DateRange(start=date(2026, 4, 1), end=date(2026, 4, 30), label="april 2026")


class DateRangeTests(unittest.TestCase):
    def test_days_inclusive(self):
        self.assertEqual(_march().days, 31)

    def test_rejects_reversed_range(self):
        with self.assertRaises(ValidationError):
            DateRange(start=date(2026, 4, 1), end=date(2026, 3, 1))

    def test_overlap_detection(self):
        a = DateRange(start=date(2026, 3, 1), end=date(2026, 4, 15))
        b = DateRange(start=date(2026, 4, 1), end=date(2026, 4, 30))
        self.assertTrue(a.overlaps(b))
        self.assertFalse(_march().overlaps(_april()))


class ComparisonSpecTests(unittest.TestCase):
    def test_month_over_month_pair(self):
        spec = ComparisonSpec(
            period_a=_march(),
            period_b=_april(),
            comparison_type="month_over_month",
            source="explicit_free_text",
        )
        self.assertEqual(spec.period_a.days, 31)
        self.assertEqual(spec.period_b.days, 30)

    def test_non_rolling_overlap_rejected(self):
        with self.assertRaises(ValidationError):
            ComparisonSpec(
                period_a=DateRange(start=date(2026, 3, 1), end=date(2026, 4, 15)),
                period_b=DateRange(start=date(2026, 4, 1), end=date(2026, 4, 30)),
                comparison_type="custom",
                source="comparison_composer",
            )

    def test_rolling_adjacent_allowed(self):
        spec = ComparisonSpec(
            period_a=DateRange(start=date(2026, 4, 24), end=date(2026, 5, 23)),
            period_b=DateRange(start=date(2026, 5, 24), end=date(2026, 6, 22)),
            comparison_type="rolling",
            source="prior_context",
        )
        self.assertEqual(spec.comparison_type, "rolling")


class AnalysisPlanTests(unittest.TestCase):
    def test_explicit_month_comparison_plan(self):
        plan = AnalysisPlan(
            intent="period_comparison",
            metric="revenue",
            dimensions=["product", "region"],
            comparison=ComparisonSpec(
                period_a=_march(),
                period_b=_april(),
                comparison_type="month_over_month",
                source="explicit_free_text",
            ),
            chart_intent="comparison_bar",
            output_sections=["summary", "comparison", "product_drivers"],
            confidence=0.94,
            reasoning_summary="Two explicit months parsed from free text.",
        )
        self.assertTrue(plan.runs_tools)
        self.assertEqual(plan.comparison.period_a.start, date(2026, 3, 1))

    def test_period_comparison_without_spec_is_rejected(self):
        with self.assertRaises(ValidationError):
            AnalysisPlan(intent="period_comparison", needs_clarification=False)

    def test_vague_comparison_becomes_clarification(self):
        plan = AnalysisPlan(
            intent="clarification",
            needs_clarification=True,
            clarification_type="comparison_dates",
            chart_intent="none",
            confidence=0.4,
            reasoning_summary="No periods given; open composer.",
        )
        self.assertFalse(plan.runs_tools)

    def test_clarification_requires_type(self):
        with self.assertRaises(ValidationError):
            AnalysisPlan(intent="clarification", needs_clarification=True)

    def test_trend_plan_single_period(self):
        plan = AnalysisPlan(
            intent="sales_trend",
            metric="revenue",
            primary_period=DateRange(start=date(2026, 5, 24), end=date(2026, 6, 22)),
            chart_intent="line",
            output_sections=["summary", "trend"],
            confidence=0.9,
            reasoning_summary="Last 30 days trend.",
        )
        self.assertTrue(plan.runs_tools)
        self.assertIsNone(plan.comparison)


class AnalysisResultTests(unittest.TestCase):
    def _comparison_plan(self) -> AnalysisPlan:
        return AnalysisPlan(
            intent="period_comparison",
            metric="revenue",
            comparison=ComparisonSpec(
                period_a=_march(),
                period_b=_april(),
                comparison_type="month_over_month",
                source="comparison_composer",
            ),
            chart_intent="comparison_bar",
            output_sections=["comparison"],
            confidence=1.0,
            reasoning_summary="composer",
        )

    def test_result_preserves_exact_periods(self):
        plan = self._comparison_plan()
        result = AnalysisResult(
            plan_id="p1",
            tenant_id="t1",
            supplier_id="s1",
            resolved_plan=plan,
            comparison_period=_march(),  # Period A baseline
            primary_period=_april(),
            source_tools=["get_supplier_kpis"],
        )
        self.assertEqual(result.comparison_period.start, date(2026, 3, 1))

    def test_result_rejects_mismatched_comparison_period(self):
        plan = self._comparison_plan()
        with self.assertRaises(ValidationError):
            AnalysisResult(
                plan_id="p1",
                tenant_id="t1",
                supplier_id="s1",
                resolved_plan=plan,
                # Wrong baseline — a hidden rolling window must be impossible.
                comparison_period=DateRange(start=date(2025, 6, 1), end=date(2025, 6, 30)),
            )

    def test_result_rejects_mismatched_primary_period(self):
        plan = AnalysisPlan(
            intent="sales_trend",
            metric="revenue",
            primary_period=DateRange(start=date(2026, 5, 24), end=date(2026, 6, 22)),
            chart_intent="line",
            confidence=0.9,
            reasoning_summary="trend",
        )
        with self.assertRaises(ValidationError):
            AnalysisResult(
                plan_id="p1",
                tenant_id="t1",
                supplier_id="s1",
                resolved_plan=plan,
                primary_period=DateRange(start=date(2026, 1, 1), end=date(2026, 6, 22)),
            )


class VerificationResultTests(unittest.TestCase):
    def test_blocking_cannot_be_approved(self):
        with self.assertRaises(ValidationError):
            VerificationResult(
                approved=True,
                severity="blocking",
                required_action="replan",
                verified_periods_match=False,
                verified_metric_match=True,
                verified_chart_match=True,
                verified_scope_match=True,
            )

    def test_unapproved_cannot_continue(self):
        with self.assertRaises(ValidationError):
            VerificationResult(
                approved=False,
                severity="warning",
                required_action="continue",
                verified_periods_match=True,
                verified_metric_match=True,
                verified_chart_match=True,
                verified_scope_match=True,
            )

    def test_clean_pass(self):
        v = VerificationResult(
            approved=True,
            severity="none",
            required_action="continue",
            verified_periods_match=True,
            verified_metric_match=True,
            verified_chart_match=True,
            verified_scope_match=True,
        )
        self.assertTrue(v.approved)


class ConversationContextTests(unittest.TestCase):
    def test_single_period_plan_is_reusable(self):
        ctx = ConversationAnalysisContext(
            last_resolved_plan=AnalysisPlan(
                intent="sales_trend",
                metric="revenue",
                primary_period=DateRange(start=date(2026, 5, 24), end=date(2026, 6, 22)),
                chart_intent="line",
                confidence=0.9,
                reasoning_summary="trend",
            )
        )
        self.assertTrue(ctx.has_reusable_period)

    def test_comparison_plan_not_reusable(self):
        ctx = ConversationAnalysisContext(
            last_resolved_plan=AnalysisPlan(
                intent="period_comparison",
                metric="revenue",
                comparison=ComparisonSpec(
                    period_a=_march(),
                    period_b=_april(),
                    comparison_type="month_over_month",
                    source="explicit_free_text",
                ),
                chart_intent="comparison_bar",
                confidence=1.0,
                reasoning_summary="x",
            )
        )
        self.assertFalse(ctx.has_reusable_period)

    def test_awaiting_clarification_blocks_reuse(self):
        ctx = ConversationAnalysisContext(awaiting_clarification="comparison_dates")
        self.assertFalse(ctx.has_reusable_period)


if __name__ == "__main__":
    unittest.main()
