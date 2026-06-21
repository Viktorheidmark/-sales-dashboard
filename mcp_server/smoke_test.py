"""
Smoke test for MCP query functions.

Calls each query function directly against the live database.
Does NOT require an MCP client or transport layer.

Usage (from project root, with backend/.venv active):
    python -m mcp_server.smoke_test

The script prints a summary for each tool and exits non-zero on any failure.
"""

import json
import sys
import traceback
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from mcp_server.db import get_session
from mcp_server.query_helpers import (
    query_declining_products,
    query_market_share,
    query_sales_by_region,
    query_sales_over_time,
    query_supplier_kpis,
    query_top_products,
)

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"

TODAY = datetime.now(tz=timezone.utc).date()


def _ago(days: int) -> date:
    return TODAY - timedelta(days=days)


def get_supplier_id(db, name: str) -> str:
    from sqlalchemy import text
    row = db.execute(text("SELECT id FROM suppliers WHERE name = :name"), {"name": name}).fetchone()
    if row is None:
        raise RuntimeError(f"Supplier not found: '{name}'. Run the seed script first.")
    return str(row.id)


def run(label: str, fn, *args, assertions=None, **kwargs):
    """
    Call fn(*args, **kwargs), print a preview, then run any assertion callables
    against the result dict.  Each assertion is (description, callable(result)->bool).
    """
    try:
        result = fn(*args, **kwargs)
        preview = json.dumps(result, indent=2)[:600]
        print(f"\n{PASS} {label}")
        print(preview)
        if len(json.dumps(result)) > 600:
            print("  ... (truncated)")

        if assertions:
            all_ok = True
            for desc, check in assertions:
                ok = check(result)
                marker = PASS if ok else FAIL
                print(f"    {marker} assert: {desc}")
                if not ok:
                    all_ok = False
            if not all_ok:
                return False
        return True
    except Exception:
        print(f"\n{FAIL} {label}")
        traceback.print_exc()
        return False


def assert_date_range(start: date, end: date):
    """Return an assertion tuple checking returned date_range matches expected."""
    def _check(result):
        dr = result.get("date_range", {})
        return dr.get("start") == start.isoformat() and dr.get("end") == end.isoformat()
    return (
        f"date_range.start={start} date_range.end={end}",
        _check,
    )


def assert_series_within(start: date, end: date, granularity: str = "day"):
    """
    Return an assertion tuple checking that every period in 'series' is
    consistent with the requested date range, accounting for DATE_TRUNC
    bucket-label behaviour:

    - day   : period must be exactly within [start, end].
    - week  : the first bucket may begin up to 6 days before start (because
              DATE_TRUNC('week', ...) labels the bucket by the Monday that
              precedes or equals start_date).  All subsequent buckets must
              be <= end.
    - month : the first bucket may begin on the 1st of start_date's month
              (DATE_TRUNC('month', ...) labels the bucket by the 1st).
              All subsequent buckets must be <= end.

    In every case the bucket label must not exceed end_date, because
    DATE_TRUNC can never produce a label beyond the latest order_date
    included by the SQL WHERE clause.
    """
    if granularity == "week":
        # Monday of the week containing start_date — at most 6 days earlier
        days_since_monday = start.weekday()  # Mon=0 … Sun=6
        earliest_allowed = start - timedelta(days=days_since_monday)
    elif granularity == "month":
        earliest_allowed = start.replace(day=1)
    else:
        earliest_allowed = start  # day granularity: exact match required

    def _check(result):
        series = result.get("series", [])
        if not series:
            return True  # no data is acceptable for narrow windows
        for i, point in enumerate(series):
            period = date.fromisoformat(point["period"])
            # First bucket may start as early as the truncation boundary;
            # all buckets must not exceed end_date.
            lower = earliest_allowed if i == 0 else start
            if period < lower or period > end:
                print(f"      out-of-range period: {period} not in [{lower}, {end}] (bucket {i})")
                return False
        return True

    return (
        f"all series periods consistent with [{start}, {end}] at {granularity} granularity",
        _check,
    )


def assert_top_product_is(sku: str):
    def _check(result):
        products = result.get("products", [])
        if not products:
            return False
        return products[0].get("sku") == sku
    return (f"rank-1 product is {sku}", _check)


def assert_market_share_leading(result):
    return result.get("market_share_pct", 0) > 50


def assert_cold_brew_declining(result):
    for p in result.get("products", []):
        if p.get("sku") in ("NCO-003", "NCO-006"):
            return p.get("revenue_change", 0) < 0
    return True  # not always in top-5 decliners, acceptable


def main():
    db = get_session()
    try:
        nordic_id = get_supplier_id(db, "Nordic Coffee AB")
        snacks_id = get_supplier_id(db, "Fresh Snacks Ltd")
        clean_id  = get_supplier_id(db, "Clean Home Co")
    finally:
        db.close()

    print(f"\nToday                        : {TODAY}")
    print(f"Nordic Coffee AB supplier_id : {nordic_id}")
    print(f"Fresh Snacks Ltd supplier_id : {snacks_id}")
    print(f"Clean Home Co supplier_id    : {clean_id}")

    # Pre-compute explicit date windows used across tests
    last_90_start  = _ago(90)
    last_60_start  = _ago(60)
    last_179_start = _ago(179)
    hist_start     = date(2025, 10, 1)
    hist_end       = date(2025, 12, 31)

    results = []
    db = get_session()
    try:
        # ------------------------------------------------------------------
        # KPIs
        # ------------------------------------------------------------------
        results.append(run(
            "get_supplier_kpis — Nordic Coffee AB (default 179-day window)",
            query_supplier_kpis, db, nordic_id,
            assertions=[
                assert_date_range(last_179_start, TODAY),
            ],
        ))

        results.append(run(
            "get_supplier_kpis — Fresh Snacks Ltd (last 90 days)",
            query_supplier_kpis, db, snacks_id,
            start_date=last_90_start,
            end_date=TODAY,
            assertions=[
                assert_date_range(last_90_start, TODAY),
            ],
        ))

        results.append(run(
            "get_supplier_kpis — Nordic Coffee AB (historical Q4-2025)",
            query_supplier_kpis, db, nordic_id,
            start_date=hist_start,
            end_date=hist_end,
            assertions=[
                assert_date_range(hist_start, hist_end),
            ],
        ))

        # ------------------------------------------------------------------
        # Sales over time
        # ------------------------------------------------------------------
        results.append(run(
            "get_sales_over_time — Nordic Coffee AB monthly (default window)",
            query_sales_over_time, db, nordic_id,
            granularity="month",
            assertions=[
                assert_date_range(last_179_start, TODAY),
                assert_series_within(last_179_start, TODAY, "month"),
            ],
        ))

        results.append(run(
            "get_sales_over_time — Nordic Coffee AB weekly (last 60 days)",
            query_sales_over_time, db, nordic_id,
            start_date=last_60_start,
            end_date=TODAY,
            granularity="week",
            assertions=[
                assert_date_range(last_60_start, TODAY),
                assert_series_within(last_60_start, TODAY, "week"),
            ],
        ))

        results.append(run(
            "get_sales_over_time — Fresh Snacks Ltd daily (last 90 days)",
            query_sales_over_time, db, snacks_id,
            start_date=last_90_start,
            end_date=TODAY,
            granularity="day",
            assertions=[
                assert_date_range(last_90_start, TODAY),
                assert_series_within(last_90_start, TODAY, "day"),
            ],
        ))

        results.append(run(
            "get_sales_over_time — Nordic Coffee AB monthly (historical Q4-2025)",
            query_sales_over_time, db, nordic_id,
            start_date=hist_start,
            end_date=hist_end,
            granularity="month",
            assertions=[
                assert_date_range(hist_start, hist_end),
                assert_series_within(hist_start, hist_end, "month"),
            ],
        ))

        # ------------------------------------------------------------------
        # Top products
        # ------------------------------------------------------------------
        results.append(run(
            "get_top_products — Nordic Coffee AB top 5 (default window)",
            query_top_products, db, nordic_id,
            limit=5,
            assertions=[
                assert_top_product_is("NCO-001"),  # Espresso Dark Roast must be #1
            ],
        ))

        results.append(run(
            "get_top_products — Nordic Coffee AB top 3 in Stockholm (last 90 days)",
            query_top_products, db, nordic_id,
            start_date=last_90_start,
            end_date=TODAY,
            limit=3,
            region="Stockholm",
            assertions=[
                assert_date_range(last_90_start, TODAY),
            ],
        ))

        # ------------------------------------------------------------------
        # Sales by region
        # ------------------------------------------------------------------
        results.append(run(
            "get_sales_by_region — Nordic Coffee AB (default window)",
            query_sales_by_region, db, nordic_id,
            assertions=[
                assert_date_range(last_179_start, TODAY),
            ],
        ))

        results.append(run(
            "get_sales_by_region — Fresh Snacks Ltd (last 90 days)",
            query_sales_by_region, db, snacks_id,
            start_date=last_90_start,
            end_date=TODAY,
            assertions=[
                assert_date_range(last_90_start, TODAY),
            ],
        ))

        # ------------------------------------------------------------------
        # Market share
        # ------------------------------------------------------------------
        results.append(run(
            "get_market_share — Nordic Coffee AB in Coffee (default window)",
            query_market_share, db, nordic_id, "Coffee",
            assertions=[
                ("Nordic Coffee AB holds >50% Coffee share",
                 assert_market_share_leading),
                assert_date_range(last_179_start, TODAY),
            ],
        ))

        results.append(run(
            "get_market_share — Clean Home Co in Household (last 90 days)",
            query_market_share, db, clean_id, "Household",
            start_date=last_90_start,
            end_date=TODAY,
            assertions=[
                assert_date_range(last_90_start, TODAY),
            ],
        ))

        # ------------------------------------------------------------------
        # Declining products
        # ------------------------------------------------------------------
        results.append(run(
            "get_declining_products — Nordic Coffee AB (30 days, top 5)",
            query_declining_products, db, nordic_id,
            days=30, limit=5,
            assertions=[
                ("Cold Brew Can (NCO-003/NCO-006) has negative revenue_change if present",
                 assert_cold_brew_declining),
            ],
        ))

        results.append(run(
            "get_declining_products — Fresh Snacks Ltd (30 days, top 3)",
            query_declining_products, db, snacks_id,
            days=30, limit=3,
        ))

    finally:
        db.close()

    passed = sum(results)
    total = len(results)
    print(f"\n{'─'*50}")
    print(f"Smoke test complete: {passed}/{total} passed")
    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
