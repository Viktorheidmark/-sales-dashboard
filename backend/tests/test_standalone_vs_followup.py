"""
Focused tests for standalone vs follow-up context behavior.

Rule: a standalone question with no explicit period defaults to the full available
dataset. A follow-up modifier inherits prior context.
"""

import os
import unittest
from datetime import date
from unittest.mock import patch

from app.schemas.analysis_plan import AnalysisPlan, AnalysisFilters, TimePeriod, VisualizationSpec
from app.services.follow_up_context import AnalysisContext, plan_nl_context_followup
from app.services.intent_router import (
    PriorTurnContext,
    plan_forced_tools,
    _period_args_from_message,
)
from app.services.period_utils import default_data_bounds, latest_completed_date
from app.services.tool_planner import plan_deterministic_tools, resolve_tool_plans


UI_START = "2026-03-25"   # simulated 90-day UI preset
UI_END   = "2026-06-23"


def _full_range() -> tuple[str, str]:
    """Returns the expected full-dataset bounds."""
    mn, mx = default_data_bounds()
    return mn.isoformat(), mx.isoformat()


def _prior_stockholm_30d() -> PriorTurnContext:
    """Prior context: top products in Stockholm, last 30 days."""
    prior_start = "2026-05-24"
    prior_end   = "2026-06-22"
    return PriorTurnContext(
        question="Vilka produkter säljer bäst i Stockholm de senaste 30 dagarna?",
        tool_calls=("get_top_products",),
        sources=({"tool": "get_top_products",
                  "date_range": {"start": prior_start, "end": prior_end}},),
        has_chart=True,
        analysis_context={
            "prior_intent": "product_ranking",
            "start_date": prior_start,
            "end_date": prior_end,
            "period_kind": "rolling_30",
            "region": "Stockholm",
            "limit": 5,
            "prior_tool_calls": ["get_top_products"],
        },
    )


class StandaloneQuestionPeriodTests(unittest.TestCase):
    """Standalone questions must default to full_history, never inherit prior context."""

    def test_fresh_stockholm_question_uses_full_history(self):
        """Test 1: 'Vilka produkter säljer bäst i Stockholm?' → Stockholm + full period."""
        plans = plan_forced_tools(
            "Vilka produkter säljer bäst i Stockholm?",
            "Coca-Cola Europacific Partners Sverige",
            start_date=UI_START,
            end_date=UI_END,
            prior_context=None,
        )
        self.assertTrue(plans, "Expected at least one tool plan")
        top = next((p for p in plans if p.tool_name == "get_top_products"), None)
        self.assertIsNotNone(top, "Expected get_top_products plan")
        mn, mx = _full_range()
        self.assertEqual(top.args["start_date"], mn, "Start date must be full dataset start")
        self.assertEqual(top.args["end_date"], mx, "End date must be full dataset end")
        self.assertEqual(top.args.get("region"), "Stockholm")

    def test_period_args_no_explicit_period_returns_full_history(self):
        """_period_args_from_message with no period phrase → full_history."""
        args = _period_args_from_message(
            "Vilka produkter säljer bäst?",
            start_date=UI_START,
            end_date=UI_END,
        )
        mn, mx = _full_range()
        self.assertEqual(args["start_date"], mn)
        self.assertEqual(args["end_date"], mx)
        self.assertEqual(args["_period_kind"], "full_history")
        self.assertFalse(args["_period_explicit"])

    def test_period_args_explicit_30d_overrides(self):
        """Explicit 'senaste 30 dagarna' in message wins over full_history default."""
        args = _period_args_from_message(
            "Vilka produkter säljer bäst senaste 30 dagarna?",
            start_date=UI_START,
            end_date=UI_END,
        )
        self.assertEqual(args["_period_kind"], "rolling_30")
        self.assertTrue(args["_period_explicit"])


class StandaloneAfterPriorContextTests(unittest.TestCase):
    """Standalone questions after prior context must NOT inherit prior region/period."""

    def test_top3_standalone_does_not_inherit_stockholm_or_30d(self):
        """Test 2: 'Ge mig top 3 bästa produkterna' after Stockholm/30d → full period, all regions."""
        prior = _prior_stockholm_30d()
        plans = plan_deterministic_tools(
            "Ge mig top 3 bästa produkterna",
            "Coca-Cola Europacific Partners Sverige",
            start_date=UI_START,
            end_date=UI_END,
            prior_context=prior,
        )
        # Should NOT be routed as a follow-up; deterministic returns [] for standalones
        # (AI planner handles them). Just verify plan_nl_context_followup is silent:
        from app.services.follow_up_context import AnalysisContext, plan_nl_context_followup
        ctx = AnalysisContext.from_dict(prior.analysis_context)
        nl = plan_nl_context_followup("Ge mig top 3 bästa produkterna", ctx)
        self.assertEqual(nl, [], "Must NOT be treated as a bare limit modifier")

    def test_market_share_standalone_does_not_inherit_stockholm(self):
        """Test 3: 'Hur stor marknadsandel har vi inom Läsk?' after Stockholm/30d → Läsk, full period."""
        prior = _prior_stockholm_30d()
        plans = plan_forced_tools(
            "Hur stor marknadsandel har vi inom Läsk?",
            "Coca-Cola Europacific Partners Sverige",
            start_date=UI_START,
            end_date=UI_END,
            prior_context=prior,
        )
        ms = next((p for p in plans if p.tool_name == "get_market_share"), None)
        self.assertIsNotNone(ms, "Expected market share plan")
        # Must NOT carry Stockholm region
        self.assertNotEqual(ms.args.get("region"), "Stockholm")
        # Must use full history, not 30d
        mn, mx = _full_range()
        self.assertEqual(ms.args["start_date"], mn)

    def test_show_starkaste_produkter_standalone_no_region_inheritance(self):
        """'Visa våra starkaste produkter inom Läsk' is standalone → not a NL modifier."""
        prior = _prior_stockholm_30d()
        ctx = AnalysisContext.from_dict(prior.analysis_context)
        nl = plan_nl_context_followup("Visa våra starkaste produkter inom Läsk", ctx)
        self.assertEqual(nl, [], "Full sentence must not be treated as a follow-up modifier")


class FollowUpModifierTests(unittest.TestCase):
    """Genuine follow-up modifiers must still inherit prior context."""

    def _product_ranking_ctx(self) -> AnalysisContext:
        ytd_start = f"{date.today().year}-01-01"
        ytd_end = latest_completed_date().isoformat()
        return AnalysisContext(
            prior_intent="product_ranking",
            start_date=ytd_start,
            end_date=ytd_end,
            period_kind="year_to_date",
            region="Stockholm",
            category="Läsk",
            limit=5,
            prior_tool_calls=["get_top_products"],
        )

    def test_top3_bare_modifier_inherits_prior(self):
        """Test 4: bare 'top 3 då?' inherits prior period, region, category."""
        ctx = self._product_ranking_ctx()
        plans = plan_nl_context_followup("top 3 då?", ctx)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_top_products")
        self.assertEqual(plans[0].args["limit"], 3)
        # Preserves prior context
        self.assertEqual(plans[0].args.get("region"), "Stockholm")
        self.assertEqual(plans[0].args.get("category_name"), "Läsk")
        # Period preserved from prior (not inherited from the UI's 90-day range)
        self.assertEqual(plans[0].args["start_date"], ctx.start_date)

    def test_ytd_period_modifier_inherits_intent(self):
        """Test 5: 'under hela året då?' changes only the period, preserves intent."""
        ctx = AnalysisContext(
            prior_intent="product_ranking",
            start_date="2026-03-25",
            end_date="2026-06-22",
            period_kind="rolling_30",
            region=None,
            category="Läsk",
            limit=10,
            prior_tool_calls=["get_top_products"],
        )
        plans = plan_nl_context_followup("under hela året då?", ctx)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].tool_name, "get_top_products")
        self.assertEqual(plans[0].args.get("_period_kind"), "year_to_date")
        self.assertEqual(plans[0].args.get("category_name"), "Läsk")
        start = date.fromisoformat(plans[0].args["start_date"])
        self.assertEqual(start.month, 1)

    def test_bare_stockholm_modifier_inherits_intent(self):
        """Bare 'i Stockholm då?' is a follow-up modifier, not a standalone."""
        ctx = AnalysisContext(
            prior_intent="product_ranking",
            start_date="2026-01-01",
            end_date="2026-06-22",
            period_kind="year_to_date",
            region=None,
            category="Läsk",
            limit=5,
            prior_tool_calls=["get_top_products"],
        )
        plans = plan_nl_context_followup("i Stockholm då?", ctx)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].args.get("region"), "Stockholm")


class YTDFreshQuestionTests(unittest.TestCase):
    """Test 6: fresh YTD question gets current-year period, no stale filters."""

    def test_ytd_fresh_question_no_stale_region(self):
        """'Hur går det för oss hittills i år?' → YTD, no region."""
        plans = plan_forced_tools(
            "Hur går det för oss hittills i år?",
            "Coca-Cola Europacific Partners Sverige",
            start_date=UI_START,
            end_date=UI_END,
            prior_context=None,
        )
        self.assertTrue(plans)
        for p in plans:
            self.assertNotEqual(p.args.get("region"), "Stockholm",
                                "YTD fresh question must not inherit any region")
            start_s = p.args.get("start_date", "")
            if start_s:
                start_d = date.fromisoformat(start_s)
                self.assertEqual(start_d.year, date.today().year,
                                 "YTD question must resolve to current year")
                self.assertEqual(start_d.month, 1)

    def test_ui_90d_preset_does_not_leak_into_standalone(self):
        """The UI 90-day preset must never appear as a period in a standalone answer."""
        args = _period_args_from_message(
            "Ge mig top 3 bästa produkterna",
            start_date=UI_START,
            end_date=UI_END,
        )
        # Must NOT return the UI's 90-day window
        self.assertNotEqual(args.get("start_date"), UI_START,
                             "UI start must not leak into standalone question")
        self.assertNotEqual(args.get("start_date"), "2026-03-25")
        self.assertEqual(args["_period_kind"], "full_history")


class PlannerFullHistoryDefaultTests(unittest.TestCase):
    """Planner path: unspecified period resolves to full_history."""

    def test_normalizer_unspecified_period_gives_full_history(self):
        """When AI planner says unspecified period, normalizer uses full_history."""
        from app.services.plan_normalizer import normalize_plan
        plan = AnalysisPlan(
            intent="product_ranking",
            time_period=TimePeriod(kind="unspecified"),
            filters=AnalysisFilters(regions=["Stockholm"]),
            confidence=0.90,
        )
        result = normalize_plan(
            plan,
            "Vilka produkter säljer bäst i Stockholm?",
            "Coca-Cola Europacific Partners Sverige",
            ui_start=UI_START,
            ui_end=UI_END,
        )
        self.assertFalse(result.use_fallback)
        self.assertEqual(result.meta.period_kind, "full_history")
        mn, mx = _full_range()
        self.assertEqual(result.meta.resolved_start_date, mn)
        self.assertEqual(result.meta.resolved_end_date, mx)

    def test_supplier_id_never_in_standalone_plan_args(self):
        """supplier_id must never appear in any tool plan args."""
        plans = plan_forced_tools(
            "Ge mig top 3 bästa produkterna",
            "Coca-Cola Europacific Partners Sverige",
            start_date=UI_START,
            end_date=UI_END,
        )
        for p in plans:
            self.assertNotIn("supplier_id", p.args)


if __name__ == "__main__":
    unittest.main()
