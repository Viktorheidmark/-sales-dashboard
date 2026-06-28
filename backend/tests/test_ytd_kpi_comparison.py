"""Tests for YTD year-over-year KPI comparison logic."""

import sys
import unittest
from datetime import date
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from mcp_server.query_helpers import (  # noqa: E402
    is_year_to_date_range,
    prior_year_same_period,
)

from app.services.comparison_labels import kpi_comparison_label  # noqa: E402


class YtdKpiComparisonTests(unittest.TestCase):
    def test_detects_year_to_date_range(self):
        self.assertTrue(is_year_to_date_range(date(2026, 1, 1), date(2026, 6, 23)))
        self.assertFalse(is_year_to_date_range(date(2026, 3, 1), date(2026, 6, 23)))
        self.assertFalse(is_year_to_date_range(date(2025, 1, 1), date(2026, 6, 23)))

    def test_prior_year_same_period(self):
        prev_sd, prev_ed = prior_year_same_period(date(2026, 1, 1), date(2026, 6, 23))
        self.assertEqual(prev_sd, date(2025, 1, 1))
        self.assertEqual(prev_ed, date(2025, 6, 23))

    def test_ytd_comparison_label_wording(self):
        kpi = {
            "comparison_kind": "year_over_year",
            "date_range": {"start": "2026-01-01", "end": "2026-06-23"},
            "prev_date_range": {"start": "2025-01-01", "end": "2025-06-23"},
        }
        label = kpi_comparison_label(kpi)
        # Both windows are now explicit (Phase 6: exact ranges, no bare baseline).
        self.assertIn("Hittills i år (1 januari–23 juni 2026)", label)
        self.assertIn("jämfört med samma period föregående år", label)
        self.assertIn("1 januari–23 juni 2025", label)

    def test_rolling_30_day_keeps_equal_length_label(self):
        kpi = {
            "comparison_kind": "prior_equal_length",
            "date_range": {"start": "2026-05-25", "end": "2026-06-23"},
            "prev_date_range": {"start": "2026-04-25", "end": "2026-05-24"},
        }
        label = kpi_comparison_label(kpi)
        self.assertIn("Senaste 30 dagarna", label)
        self.assertIn("jämfört med föregående 30 dagar", label)
        self.assertNotIn("samma period föregående år", label)


if __name__ == "__main__":
    unittest.main()
