"""Tests for centralized human-readable period labels."""

import unittest
from datetime import date, timedelta

from app.services.chart_builder import build_chart
from app.services.comparison_labels import build_comparison_context_block
from app.services.period_labels import (
    answer_period_opening,
    answer_period_phrase,
    apply_period_labels,
    chart_period_suffix,
    infer_period_kind,
)
from app.services.period_utils import default_data_bounds, latest_completed_date


class PeriodLabelTests(unittest.TestCase):
  UI_END = latest_completed_date().isoformat()
  UI_START = (latest_completed_date() - timedelta(days=89)).isoformat()

  def test_default_90_day_answer_phrase(self):
    result = apply_period_labels(
      {
        "date_range": {"start": self.UI_START, "end": self.UI_END},
        "products": [{"product_name": "A", "revenue": 1.0}, {"product_name": "B", "revenue": 0.5}],
      },
      "Vilka produkter säljer bäst i Stockholm?",
      {"_period_kind": "ui_default", "_period_explicit": False},
      tool_name="get_top_products",
    )
    self.assertEqual(result["period_label_answer"], "de senaste 90 dagarna")
    self.assertIn("de senaste 90 dagarna", result["period_label_opening"])

  def test_default_90_day_chart_subtitle(self):
    result = apply_period_labels(
      {"date_range": {"start": self.UI_START, "end": self.UI_END}},
      "Vilka produkter säljer bäst i Stockholm?",
      {"_period_kind": "ui_default"},
      tool_name="get_top_products",
    )
    chart = build_chart("get_top_products", {
      **result,
      "products": [
        {"product_name": "Coca-Cola Zero Sugar 33 cl", "revenue": 100.0},
        {"product_name": "Coca-Cola Original 33 cl", "revenue": 80.0},
      ],
      "region_filter": "Stockholm",
    })
    assert chart is not None
    self.assertIn("senaste 90 dagarna", chart["description"])
    self.assertIn("Stockholm", chart["description"])

  def test_ytd_answer_phrase(self):
    ytd_start = f"{date.today().year}-01-01"
    ytd_end = self.UI_END
    result = apply_period_labels(
      {"date_range": {"start": ytd_start, "end": ytd_end}},
      "Vilka produkter säljer bäst i år?",
      {"_period_kind": "year_to_date", "_period_explicit": True},
      tool_name="get_top_products",
    )
    self.assertEqual(result["period_label_answer"], "hittills i år")
    self.assertIn("hittills i år", result["period_label_opening"])

  def test_full_history_phrase(self):
    data_min, data_max = default_data_bounds()
    result = apply_period_labels(
      {"date_range": {"start": data_min.isoformat(), "end": data_max.isoformat()}},
      "Hur ser försäljningen ut över hela perioden?",
      {"_period_kind": "full_history", "_period_explicit": True},
      tool_name="get_supplier_kpis",
    )
    self.assertEqual(result["period_label_answer"], "över hela tillgängliga perioden")

  def test_explicit_30_day_not_labeled_as_default_90(self):
    phrase = answer_period_phrase(
      "rolling_30",
      {"start": "2026-05-26", "end": "2026-06-24"},
      "Hur har försäljningen utvecklats de senaste 30 dagarna?",
    )
    self.assertEqual(phrase, "de senaste 30 dagarna")
    self.assertNotIn("90", phrase)
    kind = infer_period_kind(
      {"start": "2026-05-26", "end": "2026-06-24"},
      message="Hur har försäljningen utvecklats de senaste 30 dagarna?",
    )
    self.assertEqual(kind, "rolling_30")

  def test_source_date_range_unchanged_after_labeling(self):
    original_dr = {"start": self.UI_START, "end": self.UI_END}
    result = apply_period_labels(
      {"date_range": dict(original_dr), "products": []},
      "Vilka produkter säljer bäst i Stockholm?",
      {"_period_kind": "ui_default"},
      tool_name="get_top_products",
    )
    self.assertEqual(result["date_range"], original_dr)

  def test_synthesis_block_includes_period_opening(self):
    result = apply_period_labels(
      {"date_range": {"start": self.UI_START, "end": self.UI_END}, "products": []},
      "Vilka produkter säljer bäst i Stockholm?",
      {"_period_kind": "ui_default"},
      tool_name="get_top_products",
    )
    block = build_comparison_context_block(
      [("get_top_products", result)],
      "Vilka produkter säljer bäst i Stockholm?",
    )
    self.assertIn("PERIOD I SVARET", block)
    self.assertIn("de senaste 90 dagarna", block)

  def test_stockholm_example_opening(self):
    opening = answer_period_opening(
      "ui_default",
      {"start": self.UI_START, "end": self.UI_END},
    )
    self.assertEqual(opening, "Under de senaste 90 dagarna")


if __name__ == "__main__":
  unittest.main()
