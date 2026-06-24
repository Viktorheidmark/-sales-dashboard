"""Tests for structured follow-up context preservation."""

import os
import unittest
from datetime import date
from unittest.mock import patch

from app.services.follow_up_context import (
    extract_analysis_context,
    plan_from_analysis_context,
    validate_and_resolve_follow_up,
    AnalysisContext,
)
from app.services.intent_router import PriorTurnContext, plan_period_followup_tools
from app.services.period_utils import latest_completed_date
from app.services.tool_planner import resolve_tool_plans


class FollowUpContextTests(unittest.TestCase):
    UI_START = "2026-03-25"
    UI_END = "2026-06-23"

    def _ytd_end(self) -> str:
        return latest_completed_date().isoformat()

    def _ytd_context(self) -> dict:
        ytd_start = f"{date.today().year}-01-01"
        ytd_end = self._ytd_end()
        return {
            "prior_intent": "sales_overview",
            "start_date": ytd_start,
            "end_date": ytd_end,
            "period_kind": "year_to_date",
            "granularity": "month",
            "prior_tool_calls": ["get_supplier_kpis", "get_sales_over_time"],
        }

    def _prior_ytd(self) -> PriorTurnContext:
        ytd_start = f"{date.today().year}-01-01"
        ytd_end = self._ytd_end()
        return PriorTurnContext(
            question="Hur ser försäljningen ut i år?",
            tool_calls=("get_supplier_kpis", "get_sales_over_time"),
            sources=(
                {"tool": "get_supplier_kpis", "date_range": {"start": ytd_start, "end": ytd_end}},
                {"tool": "get_sales_over_time", "date_range": {"start": ytd_start, "end": ytd_end}},
            ),
            has_chart=True,
            analysis_context=self._ytd_context(),
        )

    def test_extract_prefers_query_date_range(self):
        ctx = extract_analysis_context([
            ("get_supplier_kpis", {"date_range": {"start": "2026-01-01", "end": "2026-06-21"}}),
            ("get_sales_over_time", {
                "date_range": {"start": "2026-03-01", "end": "2026-05-31"},
                "query_date_range": {"start": "2026-01-01", "end": "2026-06-21"},
                "granularity": "month",
                "_period_kind": "year_to_date",
            }),
        ], "Hur ser försäljningen ut i år?")
        self.assertEqual(ctx["start_date"], "2026-01-01")
        self.assertEqual(ctx["end_date"], "2026-06-21")
        self.assertEqual(ctx["period_kind"], "year_to_date")

    def test_ytd_weekly_drilldown_preserves_ytd_range(self):
        prior = self._prior_ytd()
        action = {
            "action": "weekly_trend",
            "label": "Visa utveckling per vecka",
            "message": "Visa utveckling per vecka i år",
            "context": prior.analysis_context,
        }
        plans = validate_and_resolve_follow_up(
            action,
            prior.question,
            list(prior.tool_calls),
            list(prior.sources),
            prior.analysis_context,
            message=action["message"],
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_sales_over_time")
        self.assertEqual(plans[0].args["granularity"], "week")
        ytd_start = f"{date.today().year}-01-01"
        self.assertEqual(plans[0].args.get("_requested_start_date"), ytd_start)
        self.assertGreaterEqual(plans[0].args["start_date"], ytd_start)
        self.assertLessEqual(plans[0].args["end_date"], self._ytd_end())
        self.assertEqual(plans[0].args.get("_period_kind"), "year_to_date")

    def test_rolling_90_weekly_preserves_range(self):
        ctx = AnalysisContext(
            start_date="2026-03-25",
            end_date="2026-06-23",
            period_kind="ui_default",
            granularity="month",
            prior_tool_calls=["get_supplier_kpis", "get_sales_over_time"],
        )
        plans = plan_from_analysis_context("weekly_trend", ctx)
        self.assertEqual(plans[0].args.get("_requested_start_date"), "2026-03-25")
        self.assertGreaterEqual(plans[0].args["start_date"], "2026-03-25")
        self.assertLessEqual(plans[0].args["end_date"], "2026-06-23")

    def test_stockholm_ranking_product_trend_preserves_region(self):
        ctx = AnalysisContext(
            start_date="2026-01-01",
            end_date="2026-06-21",
            period_kind="year_to_date",
            region="Stockholm",
            prior_tool_calls=["get_top_products"],
            product_name="Produkt A",
        )
        plans = plan_from_analysis_context("product_trend", ctx)
        self.assertEqual(plans[0].tool_name, "get_sales_over_time")
        self.assertEqual(plans[0].args["start_date"], "2026-01-01")

    def test_region_filter_preserves_ytd_period(self):
        prior = self._prior_ytd()
        prior = PriorTurnContext(
            question="Vilka produkter säljer bäst i år?",
            tool_calls=("get_top_products",),
            sources=prior.sources,
            analysis_context={
                **self._ytd_context(),
                "prior_tool_calls": ["get_top_products"],
            },
        )
        plans = validate_and_resolve_follow_up(
            {"action": "region_filter", "context": {}},
            prior.question,
            list(prior.tool_calls),
            list(prior.sources),
            prior.analysis_context,
            message="I Stockholm?",
        )
        self.assertEqual(plans[0].tool_name, "get_top_products")
        self.assertEqual(plans[0].args["region"], "Stockholm")
        self.assertEqual(plans[0].args["start_date"], f"{date.today().year}-01-01")

    def test_period_change_replaces_period_preserves_subject(self):
        ctx = AnalysisContext(
            start_date="2026-01-01",
            end_date="2026-06-21",
            period_kind="year_to_date",
            region="Stockholm",
            prior_tool_calls=["get_top_products"],
        )
        plans = plan_from_analysis_context("period_change", ctx, message="förra året då?")
        self.assertEqual(plans[0].tool_name, "get_top_products")
        self.assertEqual(plans[0].args["region"], "Stockholm")
        self.assertEqual(plans[0].args["start_date"], f"{date.today().year - 1}-01-01")
        self.assertEqual(plans[0].args["end_date"], f"{date.today().year - 1}-12-31")

    def test_ui_default_cannot_override_structured_follow_up(self):
        with patch.dict(os.environ, {"USE_AI_PLANNER": "true"}):
            prior = self._prior_ytd()
            action = {
                "action": "weekly_trend",
                "label": "Visa utveckling per vecka",
                "message": "Visa utveckling per vecka i år",
            }
            res = resolve_tool_plans(
                action["message"],
                "Orkla Snacks Sverige",
                self.UI_START,
                self.UI_END,
                prior_context=prior,
                follow_up_action=action,
                injected_plan=None,
            )
        self.assertEqual(res.source, "deterministic")
        self.assertEqual(res.plans[0].args.get("_requested_start_date"), f"{date.today().year}-01-01")
        self.assertNotEqual(res.plans[0].args.get("_requested_start_date"), self.UI_START)

    def test_client_cannot_override_dates_in_follow_up_context(self):
        prior = self._prior_ytd()
        tampered = {
            "action": "weekly_trend",
            "context": {
                "start_date": self.UI_START,
                "end_date": self.UI_END,
                "period_kind": "ui_default",
            },
        }
        plans = validate_and_resolve_follow_up(
            tampered,
            prior.question,
            list(prior.tool_calls),
            list(prior.sources),
            prior.analysis_context,
        )
        self.assertEqual(plans[0].args.get("_requested_start_date"), f"{date.today().year}-01-01")
        self.assertNotEqual(plans[0].args.get("_requested_start_date"), self.UI_START)

    def test_period_followup_still_works_without_structured_action(self):
        prior = PriorTurnContext(
            question="Hur såg försäljningen ut senaste veckan?",
            tool_calls=("get_sales_over_time",),
            sources=({"date_range": {"start": "2026-06-16", "end": "2026-06-22"}},),
        )
        plans = plan_period_followup_tools(
            "senaste 30 dagarna då?",
            prior,
            "Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(plans[0].args["start_date"][:10], "2026-05-25")


if __name__ == "__main__":
    unittest.main()
