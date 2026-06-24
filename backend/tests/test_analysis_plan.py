"""Tests for AnalysisPlan schema validation."""

import unittest

from pydantic import ValidationError

from app.schemas.analysis_plan import AnalysisPlan, TimePeriod


class AnalysisPlanSchemaTests(unittest.TestCase):
    def test_minimal_valid_plan(self):
        plan = AnalysisPlan.model_validate({
            "intent": "sales_trend",
            "time_period": {"kind": "year_to_date"},
            "metrics": ["revenue"],
            "confidence": 0.9,
        })
        self.assertEqual(plan.intent, "sales_trend")
        self.assertEqual(plan.time_period.kind, "year_to_date")

    def test_full_plan_shape(self):
        raw = {
            "intent": "product_ranking",
            "time_period": {"kind": "year_to_date", "days": None, "start_date": None, "end_date": None},
            "metrics": ["revenue", "orders"],
            "dimensions": ["product", "time"],
            "filters": {"product_names": [], "brand_names": [], "regions": [], "category": None},
            "comparison": {"kind": "none", "targets": []},
            "visualization": {"primary": "bar_ranked", "granularity": "month"},
            "needs_deep_dive": False,
            "confidence": 0.92,
            "clarification_needed": False,
            "clarification_question": None,
        }
        plan = AnalysisPlan.model_validate(raw)
        self.assertEqual(plan.visualization.primary, "bar_ranked")

    def test_invalid_metric_stripped(self):
        plan = AnalysisPlan.model_validate({
            "intent": "sales_overview",
            "metrics": ["revenue", "supplier_id", "sql_injection"],
        })
        self.assertEqual(plan.metrics, ["revenue"])

    def test_confidence_bounds(self):
        with self.assertRaises(ValidationError):
            AnalysisPlan(confidence=1.5)

    def test_rolling_days_period(self):
        tp = TimePeriod(kind="rolling_days", days=30)
        self.assertEqual(tp.days, 30)


if __name__ == "__main__":
    unittest.main()
