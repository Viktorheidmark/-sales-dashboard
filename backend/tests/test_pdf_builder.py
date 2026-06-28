"""Tests for tenant-aware PDF chart coloring."""

import unittest

from app.services.pdf_builder import _draw_pdf_header, _render_chart_png
from app.services.tenant_theme import (
    COMPARISON_BASELINE_COLOR,
    SOLVIGO_ACCENT_COLOR,
    change_text_color,
    pdf_header_accent_color,
    resolve_bar_fill_colors,
    tenant_chart_theme_for_supplier,
)


def _comparison_chart(y_prior: float, y_current: float, *, variant: str = "period_comparison") -> dict:
    return {
        "chart_type": "bar_chart",
        "chart_variant": variant,
        "x_key": "label",
        "y_key": "revenue",
        "emphasis_index": 1,
        "data": [
            {"label": "Jämförelseperiod", "revenue": y_prior},
            {"label": "Analyserad period", "revenue": y_current},
        ],
    }


class TenantThemeLookupTests(unittest.TestCase):
    def test_coca_cola_red(self):
        self.assertEqual(
            tenant_chart_theme_for_supplier("Coca-Cola Europacific Partners Sverige").chart_primary,
            "#C62828",
        )

    def test_pepsi_blue(self):
        self.assertEqual(tenant_chart_theme_for_supplier("PepsiCo Northern Europe").chart_primary, "#1463D8")

    def test_orkla_orange(self):
        self.assertEqual(tenant_chart_theme_for_supplier("Orkla Snacks Sverige").chart_primary, "#E56A25")

    def test_estrella_violet(self):
        self.assertEqual(tenant_chart_theme_for_supplier("Estrella AB").chart_primary, "#6C3CCB")


class PeriodComparisonBarColorTests(unittest.TestCase):
    def _colors(self, supplier_name: str, variant: str = "period_comparison") -> list[str]:
        chart = _comparison_chart(1_000_000, 1_200_000, variant=variant)
        return resolve_bar_fill_colors(
            chart,
            [row["revenue"] for row in chart["data"]],
            supplier_name=supplier_name,
        )

    def test_coca_cola_gray_baseline_red_analyzed(self):
        self.assertEqual(
            self._colors("Coca-Cola Europacific Partners Sverige"),
            [COMPARISON_BASELINE_COLOR, "#C62828"],
        )

    def test_pepsi_gray_baseline_blue_analyzed(self):
        self.assertEqual(
            self._colors("PepsiCo Northern Europe"),
            [COMPARISON_BASELINE_COLOR, "#1463D8"],
        )

    def test_orkla_gray_baseline_orange_analyzed(self):
        self.assertEqual(
            self._colors("Orkla Snacks Sverige"),
            [COMPARISON_BASELINE_COLOR, "#E56A25"],
        )

    def test_estrella_gray_baseline_violet_analyzed(self):
        self.assertEqual(
            self._colors("Estrella AB"),
            [COMPARISON_BASELINE_COLOR, "#6C3CCB"],
        )

    def test_legacy_decline_comparison_variant_uses_same_palette(self):
        self.assertEqual(
            self._colors("Coca-Cola Europacific Partners Sverige", variant="decline_comparison"),
            [COMPARISON_BASELINE_COLOR, "#C62828"],
        )

    def test_negative_comparison_keeps_tenant_bar_not_semantic_red(self):
        chart = _comparison_chart(1_200_000, 900_000)
        colors = resolve_bar_fill_colors(
            chart,
            [row["revenue"] for row in chart["data"]],
            supplier_name="Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(colors, [COMPARISON_BASELINE_COLOR, "#C62828"])
        self.assertNotIn("#ef4444", colors)

    def test_negative_change_text_stays_semantic_red(self):
        self.assertEqual(change_text_color(-12.5), "#ef4444")
        self.assertEqual(change_text_color(8.0), "#16a34a")


class PdfHeaderAccentTests(unittest.TestCase):
    def test_coca_cola_header_red(self):
        self.assertEqual(pdf_header_accent_color("Coca-Cola Europacific Partners Sverige"), "#C62828")

    def test_pepsi_header_blue(self):
        self.assertEqual(pdf_header_accent_color("PepsiCo Northern Europe"), "#1463D8")

    def test_orkla_header_orange(self):
        self.assertEqual(pdf_header_accent_color("Orkla Snacks Sverige"), "#E56A25")

    def test_estrella_header_violet(self):
        self.assertEqual(pdf_header_accent_color("Estrella AB"), "#6C3CCB")

    def test_unknown_tenant_falls_back_to_solvigo_blue(self):
        self.assertEqual(pdf_header_accent_color(""), SOLVIGO_ACCENT_COLOR)
        self.assertEqual(pdf_header_accent_color("Unknown Supplier AB"), SOLVIGO_ACCENT_COLOR)

    def test_header_draw_uses_tenant_accent_for_symbol_and_sales_intelligence(self):
        """Canvas mock verifies accent is applied to symbol + Sales Intelligence, Solvigo stays white."""
        from unittest.mock import MagicMock
        from reportlab.lib.colors import HexColor, white

        canvas = MagicMock()
        canvas.stringWidth.side_effect = lambda text, *_a, **_k: float(len(text) * 5)

        _draw_pdf_header(
            canvas,
            page_w=500,
            page_h=800,
            margin_l=50,
            margin_r=50,
            supplier_name="Coca-Cola Europacific Partners Sverige",
        )

        fill_colors = [call.args[0] for call in canvas.setFillColor.call_args_list]
        accent = HexColor("#C62828")
        self.assertIn(accent, fill_colors)
        self.assertIn(white, fill_colors)
        stroke_colors = [call.args[0] for call in canvas.setStrokeColor.call_args_list]
        self.assertIn(accent, stroke_colors)


class PdfChartRenderSmokeTests(unittest.TestCase):
    def test_render_comparison_png_bytes_for_coca_cola(self):
        chart = _comparison_chart(500_000, 420_000)
        png = _render_chart_png(
            chart,
            supplier_name="Coca-Cola Europacific Partners Sverige",
        )
        self.assertGreater(len(png), 1000)
        self.assertTrue(png.startswith(b"\x89PNG"))

    def test_render_line_chart_uses_tenant_primary(self):
        chart = {
            "chart_type": "line_chart",
            "x_key": "label",
            "y_key": "revenue",
            "data": [
                {"label": "2026-01", "revenue": 100},
                {"label": "2026-02", "revenue": 120},
            ],
        }
        png = _render_chart_png(chart, supplier_name="Estrella AB")
        self.assertTrue(png.startswith(b"\x89PNG"))

    def test_render_ranking_bar_negative_uses_semantic_red(self):
        chart = {
            "chart_type": "bar_chart",
            "chart_variant": "decline_ranking",
            "x_key": "product_name",
            "y_key": "revenue_change",
            "data": [
                {"product_name": "A", "revenue_change": -50_000},
                {"product_name": "B", "revenue_change": 10_000},
            ],
        }
        colors = resolve_bar_fill_colors(
            chart,
            [row["revenue_change"] for row in chart["data"]],
            supplier_name="Coca-Cola Europacific Partners Sverige",
        )
        self.assertEqual(colors[0], "#ef4444")
        self.assertEqual(colors[1], "#C62828")


if __name__ == "__main__":
    unittest.main()
