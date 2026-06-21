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


def get_supplier_id(db, name: str) -> str:
    from sqlalchemy import text
    row = db.execute(text("SELECT id FROM suppliers WHERE name = :name"), {"name": name}).fetchone()
    if row is None:
        raise RuntimeError(f"Supplier not found: '{name}'. Run the seed script first.")
    return str(row.id)


def run(label: str, fn, *args, **kwargs):
    try:
        result = fn(*args, **kwargs)
        preview = json.dumps(result, indent=2)[:600]
        print(f"\n{PASS} {label}")
        print(preview)
        if len(json.dumps(result)) > 600:
            print("  ... (truncated)")
        return True
    except Exception:
        print(f"\n{FAIL} {label}")
        traceback.print_exc()
        return False


def main():
    db = get_session()
    try:
        nordic_id = get_supplier_id(db, "Nordic Coffee AB")
        snacks_id = get_supplier_id(db, "Fresh Snacks Ltd")
        clean_id  = get_supplier_id(db, "Clean Home Co")
    finally:
        db.close()

    print(f"\nNordic Coffee AB supplier_id : {nordic_id}")
    print(f"Fresh Snacks Ltd supplier_id : {snacks_id}")
    print(f"Clean Home Co supplier_id    : {clean_id}")

    results = []

    db = get_session()
    try:
        results.append(run(
            "get_supplier_kpis — Nordic Coffee AB (all time)",
            query_supplier_kpis, db, nordic_id,
        ))
        results.append(run(
            "get_supplier_kpis — Fresh Snacks Ltd (last 90 days)",
            query_supplier_kpis, db, snacks_id,
            start_date=None, end_date=None,
        ))
        results.append(run(
            "get_sales_over_time — Nordic Coffee AB monthly",
            query_sales_over_time, db, nordic_id, granularity="month",
        ))
        results.append(run(
            "get_sales_over_time — Nordic Coffee AB weekly (last 60 days)",
            query_sales_over_time, db, nordic_id, granularity="week",
        ))
        results.append(run(
            "get_top_products — Nordic Coffee AB top 5",
            query_top_products, db, nordic_id, limit=5,
        ))
        results.append(run(
            "get_top_products — Nordic Coffee AB top 3 in Stockholm",
            query_top_products, db, nordic_id, limit=3, region="Stockholm",
        ))
        results.append(run(
            "get_sales_by_region — Nordic Coffee AB",
            query_sales_by_region, db, nordic_id,
        ))
        results.append(run(
            "get_sales_by_region — Fresh Snacks Ltd",
            query_sales_by_region, db, snacks_id,
        ))
        results.append(run(
            "get_market_share — Nordic Coffee AB in Coffee",
            query_market_share, db, nordic_id, "Coffee",
        ))
        results.append(run(
            "get_market_share — Clean Home Co in Household",
            query_market_share, db, clean_id, "Household",
        ))
        results.append(run(
            "get_declining_products — Nordic Coffee AB (30 days, top 5)",
            query_declining_products, db, nordic_id, days=30, limit=5,
        ))
        results.append(run(
            "get_declining_products — Fresh Snacks Ltd (30 days, top 3)",
            query_declining_products, db, snacks_id, days=30, limit=3,
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
