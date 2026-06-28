"""Tests for structured follow-up context preservation."""

import os
import unittest
from datetime import date
from unittest.mock import patch

from app.services.follow_up_context import (
    extract_analysis_context,
    plan_from_analysis_context,
    plan_nl_context_followup,
    validate_and_resolve_follow_up,
    AnalysisContext,
)
from app.services.intent_router import PriorTurnContext, plan_period_followup_tools
from app.services.period_utils import latest_completed_date
from app.services.tool_planner import resolve_tool_plans, plan_deterministic_tools


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
        # Date-relative expectation: a 30-day window ends on the latest completed
        # date and is weekly-aligned forward to the first complete ISO week.
        from datetime import timedelta
        from app.services.period_utils import first_complete_week_monday
        raw_start = latest_completed_date() - timedelta(days=29)
        expected_start = first_complete_week_monday(raw_start)
        self.assertEqual(plans[0].args["start_date"][:10], expected_start.isoformat())


class NLContextFollowUpTests(unittest.TestCase):
    """Tests for plan_nl_context_followup — NL modifier phrases preserve prior analysis context."""

    UI_START = "2026-03-25"
    UI_END = "2026-06-23"

    def _product_ranking_ctx(self, category: str = "Läsk", region: str | None = None, limit: int = 10) -> AnalysisContext:
        return AnalysisContext(
            prior_intent="product_ranking",
            start_date="2026-03-25",
            end_date="2026-06-23",
            period_kind="ui_default",
            granularity="",
            region=region,
            category=category,
            limit=limit,
            prior_tool_calls=["get_top_products"],
        )

    def _ytd_overview_ctx(self) -> AnalysisContext:
        ytd_start = f"{date.today().year}-01-01"
        ytd_end = latest_completed_date().isoformat()
        return AnalysisContext(
            prior_intent="sales_overview",
            start_date=ytd_start,
            end_date=ytd_end,
            period_kind="year_to_date",
            granularity="month",
            prior_tool_calls=["get_supplier_kpis", "get_sales_over_time"],
        )

    def _prior_with_ctx(self, ctx: AnalysisContext, question: str) -> PriorTurnContext:
        return PriorTurnContext(
            question=question,
            tool_calls=tuple(ctx.prior_tool_calls),
            sources=({"tool": ctx.prior_tool_calls[0], "date_range": {"start": ctx.start_date, "end": ctx.end_date}},),
            has_chart=True,
            analysis_context=ctx.to_dict(),
        )

    # Test 1: product ranking + "under hela året då?" → YTD product ranking in Läsk
    def test_product_ranking_ytd_period_change(self):
        ctx = self._product_ranking_ctx(category="Läsk")
        plans = plan_nl_context_followup("under hela året då?", ctx)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_top_products")
        self.assertEqual(plans[0].args.get("_period_kind"), "year_to_date")
        self.assertEqual(plans[0].args.get("category_name"), "Läsk")
        self.assertEqual(plans[0].args.get("limit"), 10)
        # Period must be YTD
        start = date.fromisoformat(plans[0].args["start_date"])
        self.assertEqual(start.year, date.today().year)
        self.assertEqual(start.month, 1)
        self.assertEqual(start.day, 1)

    # Test 2: product ranking + "förra året då?" → previous year product ranking, category preserved
    def test_product_ranking_previous_year(self):
        ctx = self._product_ranking_ctx(category="Läsk")
        plans = plan_nl_context_followup("förra året då?", ctx)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_top_products")
        self.assertEqual(plans[0].args.get("_period_kind"), "previous_year")
        self.assertEqual(plans[0].args.get("category_name"), "Läsk")
        start = date.fromisoformat(plans[0].args["start_date"])
        self.assertEqual(start.year, date.today().year - 1)

    # Test 3: product ranking + "över hela perioden då?" → full history
    def test_product_ranking_full_history(self):
        ctx = self._product_ranking_ctx(category="Läsk")
        plans = plan_nl_context_followup("över hela perioden då?", ctx)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].args.get("_period_kind"), "full_history")
        self.assertEqual(plans[0].args.get("category_name"), "Läsk")

    # Test 4: product ranking + "top 3 då?" → limit changes, category+period preserved
    def test_product_ranking_limit_change(self):
        ctx = self._product_ranking_ctx(category="Läsk", limit=10)
        plans = plan_nl_context_followup("top 3 då?", ctx)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_top_products")
        self.assertEqual(plans[0].args.get("limit"), 3)
        self.assertEqual(plans[0].args.get("category_name"), "Läsk")
        # Period preserved from original context
        self.assertEqual(plans[0].args.get("start_date"), "2026-03-25")

    # Test 5: YTD overview + "visa vecka för vecka" → weekly trend preserving YTD period
    def test_ytd_overview_weekly_granularity(self):
        ctx = self._ytd_overview_ctx()
        plans = plan_nl_context_followup("visa vecka för vecka", ctx)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_sales_over_time")
        self.assertEqual(plans[0].args.get("granularity"), "week")
        # Preserve YTD period
        start = date.fromisoformat(plans[0].args["start_date"])
        self.assertEqual(start.year, date.today().year)
        self.assertEqual(start.month, 1)

    # Test 6: product question + "i Stockholm då?" → adds region, preserves period + category
    def test_product_ranking_region_filter(self):
        ctx = self._product_ranking_ctx(category="Läsk")
        plans = plan_nl_context_followup("i Stockholm då?", ctx)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_top_products")
        self.assertEqual(plans[0].args.get("region"), "Stockholm")
        self.assertEqual(plans[0].args.get("start_date"), "2026-03-25")

    # Test 7: clearly unrelated question → no plans from NL context followup
    def test_unrelated_question_not_transformed(self):
        ctx = self._product_ranking_ctx()
        plans = plan_nl_context_followup(
            "Visa marknadsandelen för Läsk jämfört med konkurrenter", ctx,
        )
        self.assertEqual(plans, [])

    # Test 8: UI 90-day defaults cannot override valid prior context
    def test_ui_defaults_do_not_override_prior_context_via_resolve(self):
        ctx = self._product_ranking_ctx(category="Läsk")
        prior = self._prior_with_ctx(ctx, "Visa våra starkaste produkter inom Läsk")
        # Simulate: user sends "under hela året då?" with UI 90-day window
        plans = plan_deterministic_tools(
            "under hela året då?",
            "Coca-Cola Europacific Partners Sverige",
            start_date="2026-03-25",  # UI default
            end_date="2026-06-23",     # UI default
            prior_context=prior,
        )
        self.assertGreater(len(plans), 0)
        # Must be YTD, not the UI 90-day range
        self.assertEqual(plans[0].tool_name, "get_top_products")
        start = date.fromisoformat(plans[0].args["start_date"])
        self.assertEqual(start.month, 1)  # YTD starts Jan 1
        self.assertNotEqual(plans[0].args["start_date"], "2026-03-25")

    # Test 9: supplier scope is backend-derived — supplier_id never in plan args
    def test_supplier_id_never_in_nl_plan_args(self):
        ctx = self._product_ranking_ctx(category="Läsk")
        plans = plan_nl_context_followup("under hela året då?", ctx)
        for plan in plans:
            self.assertNotIn("supplier_id", plan.args)

    # Test: long message not treated as NL modifier
    def test_long_message_not_a_modifier(self):
        ctx = self._product_ranking_ctx()
        long_msg = "Kan du visa mig en fullständig analys av alla produkter vi säljer i samtliga regioner under hela 2026?"
        plans = plan_nl_context_followup(long_msg, ctx)
        self.assertEqual(plans, [])

    # Test: no prior context → no plans
    def test_missing_prior_context_returns_empty(self):
        ctx = AnalysisContext(prior_intent="", start_date="", end_date="")
        plans = plan_nl_context_followup("under hela året då?", ctx)
        self.assertEqual(plans, [])

    # Test: "hela perioden" (without "över") → full history
    def test_hela_perioden_without_over(self):
        ctx = self._product_ranking_ctx(category="Läsk")
        plans = plan_nl_context_followup("hela perioden då?", ctx)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].args.get("_period_kind"), "full_history")

    # Test: "i år då?" → YTD
    def test_i_ar_ytd(self):
        ctx = self._product_ranking_ctx(category="Läsk")
        plans = plan_nl_context_followup("i år då?", ctx)
        self.assertEqual(len(plans), 1)
        start = date.fromisoformat(plans[0].args["start_date"])
        self.assertEqual(start.month, 1)


if __name__ == "__main__":
    unittest.main()
