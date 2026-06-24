"""Tests for Overview 'All tid' full supplier-scoped date resolution."""

import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
_backend = _root / "backend"
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

from mcp_server.query_helpers import (  # noqa: E402
    _date_range,
    query_sales_over_time,
    query_supplier_date_bounds,
    query_supplier_kpis,
)


class OverviewAllTimeRangeTests(unittest.TestCase):
    SUPPLIER_ID = "00000000-0000-0000-0000-000000000001"
    DATA_MIN = date(2024, 6, 24)
    DATA_MAX = date(2026, 6, 22)

    def _mock_db_bounds(self) -> MagicMock:
        db = MagicMock()
        row = MagicMock()
        row.min_date = self.DATA_MIN
        row.max_date = self.DATA_MAX
        db.execute.return_value.fetchone.return_value = row
        return db

    def test_unbounded_resolves_to_supplier_data_bounds(self):
        db = self._mock_db_bounds()
        sd, ed = _date_range(None, None, db=db, supplier_id=self.SUPPLIER_ID)
        self.assertEqual(sd, self.DATA_MIN)
        self.assertEqual(ed, self.DATA_MAX)

    def test_explicit_90_day_window_unchanged(self):
        start = date(2026, 3, 26)
        end = date(2026, 6, 23)
        db = self._mock_db_bounds()
        sd, ed = _date_range(start, end, db=db, supplier_id=self.SUPPLIER_ID)
        self.assertEqual(sd, start)
        self.assertEqual(ed, end)

    def test_kpi_and_trend_share_same_bounds_when_unbounded(self):
        db = self._mock_db_bounds()

        def fake_execute(sql, params):
            result = MagicMock()
            if "MIN(o.order_date)" in str(sql):
                row = MagicMock()
                row.min_date = self.DATA_MIN
                row.max_date = self.DATA_MAX
                result.fetchone.return_value = row
                return result
            if "DATE_TRUNC" in str(sql):
                rows = []
                for month in range(6, 13):
                    rows.append(MagicMock(period=date(2024, month, 1), revenue=1000.0, orders=10, units=100))
                for year in (2025, 2026):
                    for month in range(1, 13):
                        if year == 2026 and month > 6:
                            break
                        rows.append(MagicMock(period=date(year, month, 1), revenue=1000.0, orders=10, units=100))
                result.fetchall.return_value = rows
                return result
            row = MagicMock(
                total_revenue=100.0,
                total_orders=10,
                total_units=100,
                average_order_value=10.0,
                latest_order_date=datetime.combine(self.DATA_MAX, datetime.min.time()),
            )
            result.fetchone.return_value = row
            return result

        db.execute.side_effect = fake_execute

        kpi = query_supplier_kpis(db, self.SUPPLIER_ID, None, None)
        trend = query_sales_over_time(db, self.SUPPLIER_ID, None, None, "month")

        self.assertEqual(kpi["date_range"]["start"], self.DATA_MIN.isoformat())
        self.assertEqual(kpi["date_range"]["end"], self.DATA_MAX.isoformat())
        self.assertEqual(trend["date_range"]["start"], self.DATA_MIN.isoformat())
        self.assertEqual(trend["date_range"]["end"], self.DATA_MAX.isoformat())

    def test_monthly_series_spans_multiple_years(self):
        db = self._mock_db_bounds()

        def fake_execute(sql, params):
            result = MagicMock()
            if "MIN(o.order_date)" in str(sql):
                row = MagicMock()
                row.min_date = self.DATA_MIN
                row.max_date = self.DATA_MAX
                result.fetchone.return_value = row
                return result
            rows = [
                MagicMock(period=date(2024, 6, 1), revenue=1.0, orders=1, units=1),
                MagicMock(period=date(2025, 1, 1), revenue=2.0, orders=2, units=2),
                MagicMock(period=date(2026, 6, 1), revenue=3.0, orders=3, units=3),
            ]
            result.fetchall.return_value = rows
            return result

        db.execute.side_effect = fake_execute
        trend = query_sales_over_time(db, self.SUPPLIER_ID, None, None, "month")
        years = {pt["period"][:4] for pt in trend["series"]}
        self.assertIn("2024", years)
        self.assertIn("2025", years)
        self.assertIn("2026", years)
        self.assertGreaterEqual(len(trend["series"]), 3)

    def test_query_supplier_date_bounds_fallback_without_rows(self):
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = MagicMock(min_date=None, max_date=None)
        sd, ed = query_supplier_date_bounds(db, self.SUPPLIER_ID)
        self.assertLess(sd, ed)


if __name__ == "__main__":
    unittest.main()
