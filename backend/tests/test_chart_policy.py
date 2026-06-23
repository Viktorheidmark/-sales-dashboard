import unittest

from app.services.chart_policy import ChartIntent, resolve_chart_intent, select_charts
from app.services.chart_builder import LINE_CHART, BAR_CHART, PIE_CHART


class ChartPolicyTests(unittest.TestCase):
    def _drivers(self) -> dict:
        return {
            "comparison_days": 30,
            "current_period": {"total_revenue": 120000.0, "total_orders": 48, "total_units": 320},
            "prior_period": {"total_revenue": 100000.0, "total_orders": 40, "total_units": 280},
            "gainers": [],
            "losers": [],
            "region_gainers": [],
            "region_losers": [],
        }

    def _weekly_series(self, flat: bool = False) -> dict:
        if flat:
            revs = [25000.0, 25100.0, 24900.0, 25050.0]
        else:
            revs = [25000.0, 28000.0, 31000.0, 29500.0]
        return {
            "granularity": "week",
            "_force_time_series": True,
            "_chart_intent": "time_series",
            "series": [{"period": f"2026-05-{5 + i*7:02d}", "revenue": r} for i, r in enumerate(revs)],
            "date_range": {"start": "2026-05-05", "end": "2026-06-23"},
            "limitations": [],
        }

    def test_30_day_trend_primary_is_line_chart(self):
        q = "Hur har försäljningen utvecklats de senaste 30 dagarna?"
        raw = [
            ("get_revenue_drivers", {**self._drivers(), "_chart_intent": "drivers_data"}),
            ("get_sales_over_time", self._weekly_series()),
        ]
        self.assertEqual(resolve_chart_intent(q, raw), ChartIntent.TIME_SERIES)
        charts = select_charts(q, raw)
        self.assertEqual(len(charts), 1)
        self.assertEqual(charts[0]["chart_type"], LINE_CHART)
        self.assertEqual(charts[0]["chart_role"], "primary")
        self.assertNotEqual(charts[0].get("chart_variant"), "decline_comparison")

    def test_30_day_trend_excludes_secondary_period_bar(self):
        q = "Hur har försäljningen utvecklats de senaste 30 dagarna?"
        raw = [
            ("get_revenue_drivers", {**self._drivers(), "_chart_intent": "drivers_data"}),
            ("get_sales_over_time", self._weekly_series()),
        ]
        charts = select_charts(q, raw)
        titles = [c.get("title") for c in charts]
        self.assertNotIn("Jämfört med föregående period", titles)
        self.assertNotIn("Periodjämförelse", titles)
        bar_charts = [c for c in charts if c.get("chart_type") == BAR_CHART]
        self.assertEqual(bar_charts, [])

    def test_flat_trend_still_shows_line_chart(self):
        q = "Hur har försäljningen utvecklats de senaste 30 dagarna?"
        raw = [
            ("get_revenue_drivers", self._drivers()),
            ("get_sales_over_time", self._weekly_series(flat=True)),
        ]
        charts = select_charts(q, raw)
        self.assertEqual(charts[0]["chart_type"], LINE_CHART)
        self.assertIn("stability_note", charts[0])

    def test_period_comparison_primary_is_bar(self):
        q = "Jämför senaste 30 dagarna med föregående 30 dagar"
        drivers = {**self._drivers(), "_chart_intent": "period_comparison"}
        raw = [("get_revenue_drivers", drivers)]
        self.assertEqual(resolve_chart_intent(q, raw), ChartIntent.PERIOD_COMPARISON)
        charts = select_charts(q, raw)
        self.assertEqual(len(charts), 1)
        self.assertEqual(charts[0]["chart_type"], BAR_CHART)
        self.assertEqual(charts[0]["chart_variant"], "decline_comparison")
        self.assertEqual(charts[0]["title"], "Periodjämförelse")

    def test_explicit_month_comparison_primary_is_bar(self):
        q = "Hur gick det jämfört med förra månaden?"
        drivers = {**self._drivers(), "_chart_intent": "period_comparison"}
        raw = [("get_revenue_drivers", drivers)]
        self.assertEqual(resolve_chart_intent(q, raw), ChartIntent.PERIOD_COMPARISON)
        charts = select_charts(q, raw)
        self.assertEqual(len(charts), 1)
        self.assertEqual(charts[0]["chart_type"], BAR_CHART)
        self.assertEqual(charts[0]["chart_role"], "primary")

    def test_ranking_primary_is_horizontal_bar(self):
        q = "Vilka produkter säljer bäst i Stockholm?"
        raw = [("get_top_products", {
            "region_filter": "Stockholm",
            "products": [
                {"product_name": "Produkt A", "revenue": 5000.0},
                {"product_name": "Produkt B", "revenue": 3000.0},
            ],
        })]
        charts = select_charts(q, raw)
        self.assertEqual(charts[0]["chart_type"], BAR_CHART)
        self.assertEqual(charts[0]["layout"], "horizontal")

    def test_weekly_factual_uses_kpi_comparison(self):
        q = "Hur såg försäljningen ut senaste veckan?"
        raw = [("get_sales_over_time", {
            "_chart_intent": "weekly_kpi",
            "granularity": "week",
            "series": [
                {"period": "2026-06-09", "revenue": 40000.0},
                {"period": "2026-06-16", "revenue": 45000.0},
            ],
        })]
        self.assertEqual(resolve_chart_intent(q, raw), ChartIntent.WEEKLY_KPI)
        charts = select_charts(q, raw)
        self.assertEqual(charts[0]["chart_type"], BAR_CHART)
        self.assertEqual(charts[0]["title"], "Senaste avslutade veckan")

    def test_market_share_pie(self):
        q = "Hur stor är vår marknadsandel?"
        raw = [("get_market_share", {
            "category_name": "Läsk",
            "supplier_revenue": 70000.0,
            "competitor_aggregate_revenue": 30000.0,
        })]
        charts = select_charts(q, raw)
        self.assertEqual(charts[0]["chart_type"], PIE_CHART)
        self.assertEqual(charts[0]["data"][0]["name"], "Vår andel")

    def test_product_decline_comparison(self):
        q = "Vilken produkt har tappat mest de senaste 30 dagarna?"
        raw = [("get_declining_products", {
            "comparison_days": 30,
            "products": [{
                "product_name": "OLW Grillchips",
                "revenue_change_pct": -25.0,
                "latest_period_revenue": 5000.0,
                "prior_period_revenue": 8000.0,
            }],
        })]
        charts = select_charts(q, raw)
        self.assertEqual(charts[0]["chart_variant"], "decline_comparison")

    def test_supplier_id_preserved_in_chart_source(self):
        q = "Hur har försäljningen utvecklats de senaste 30 dagarna?"
        raw = [
            ("get_revenue_drivers", {**self._drivers(), "supplier_id": "abc-123"}),
            ("get_sales_over_time", {**self._weekly_series(), "supplier_id": "abc-123"}),
        ]
        charts = select_charts(q, raw)
        self.assertEqual(charts[0]["source_tool"], "get_sales_over_time")


if __name__ == "__main__":
    unittest.main()
