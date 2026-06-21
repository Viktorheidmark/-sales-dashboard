"""
API smoke test for the Solvigo dashboard endpoints.

Requires the FastAPI server to be running:
    cd backend && uvicorn app.main:app --reload

Run from the backend/ directory:
    python -m scripts.api_smoke_test

Fetches the Nordic Coffee AB supplier_id from /api/suppliers dynamically,
then hits every dashboard endpoint and reports pass/fail.
"""

import sys
import json
from pathlib import Path

try:
    import httpx
except ImportError:
    sys.exit("httpx not installed. Run: pip install httpx")

BASE = "http://localhost:8000"
PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"


def get(path: str, params: dict = None) -> tuple[int, dict]:
    r = httpx.get(f"{BASE}{path}", params=params or {}, timeout=10)
    return r.status_code, r.json()


def check(label: str, status: int, body: dict, expect_keys: list[str]) -> bool:
    if status != 200:
        print(f"{FAIL} {label}  →  HTTP {status}: {body}")
        return False
    missing = [k for k in expect_keys if k not in body]
    if missing:
        print(f"{FAIL} {label}  →  missing keys: {missing}")
        print("  ", json.dumps(body, indent=2)[:400])
        return False
    print(f"{PASS} {label}")
    return True


def main():
    # ---- resolve Nordic Coffee supplier_id ----
    try:
        status, body = get("/api/suppliers")
    except httpx.ConnectError:
        sys.exit(f"\nCould not reach {BASE}. Is the server running?\n"
                 "  cd backend && uvicorn app.main:app --reload")

    if status != 200:
        sys.exit(f"GET /api/suppliers failed: HTTP {status}")

    suppliers = {s["name"]: s["id"] for s in body["suppliers"]}
    nordic_id = suppliers.get("Nordic Coffee AB")
    snacks_id = suppliers.get("Fresh Snacks Ltd")
    if not nordic_id:
        sys.exit("Nordic Coffee AB not found in /api/suppliers. Run seed script first.")

    print(f"\nNordic Coffee AB  →  {nordic_id}")
    print(f"Fresh Snacks Ltd  →  {snacks_id}\n")

    results = []

    # 1 — /api/suppliers
    s, b = get("/api/suppliers")
    results.append(check("GET /api/suppliers", s, b, ["suppliers"]))

    # 2 — /health
    s, b = get("/health")
    results.append(check("GET /health", s, b, ["status"]))

    # 3 — overview
    s, b = get("/api/dashboard/overview", {"supplier_id": nordic_id})
    results.append(check("GET /api/dashboard/overview", s, b,
                         ["total_revenue", "total_orders", "total_units", "date_range"]))

    # 4 — overview with date range
    s, b = get("/api/dashboard/overview", {
        "supplier_id": nordic_id, "start_date": "2025-01-01", "end_date": "2025-03-31"
    })
    results.append(check("GET /api/dashboard/overview (date range)", s, b, ["total_revenue"]))

    # 5 — sales-over-time monthly
    s, b = get("/api/dashboard/sales-over-time", {"supplier_id": nordic_id, "granularity": "month"})
    results.append(check("GET /api/dashboard/sales-over-time (monthly)", s, b, ["series", "granularity"]))

    # 6 — sales-over-time weekly
    s, b = get("/api/dashboard/sales-over-time", {"supplier_id": nordic_id, "granularity": "week"})
    results.append(check("GET /api/dashboard/sales-over-time (weekly)", s, b, ["series"]))

    # 7 — top-products default
    s, b = get("/api/dashboard/top-products", {"supplier_id": nordic_id})
    results.append(check("GET /api/dashboard/top-products (default)", s, b, ["products"]))

    # 8 — top-products filtered by region
    s, b = get("/api/dashboard/top-products", {"supplier_id": nordic_id, "region": "Stockholm", "limit": "3"})
    results.append(check("GET /api/dashboard/top-products (Stockholm, limit=3)", s, b, ["products", "region_filter"]))

    # 9 — regions
    s, b = get("/api/dashboard/regions", {"supplier_id": nordic_id})
    results.append(check("GET /api/dashboard/regions", s, b, ["regions"]))

    # 10 — regions for Fresh Snacks (Malmö pattern)
    s, b = get("/api/dashboard/regions", {"supplier_id": snacks_id})
    results.append(check("GET /api/dashboard/regions (Fresh Snacks)", s, b, ["regions"]))

    # 11 — market-share Coffee
    s, b = get("/api/dashboard/market-share", {"supplier_id": nordic_id, "category_name": "Coffee"})
    results.append(check("GET /api/dashboard/market-share (Coffee)", s, b,
                         ["market_share_pct", "supplier_revenue", "category_total_revenue"]))

    # 12 — market-share Household
    s, b = get("/api/dashboard/market-share", {
        "supplier_id": suppliers.get("Clean Home Co", nordic_id), "category_name": "Household"
    })
    results.append(check("GET /api/dashboard/market-share (Household)", s, b, ["market_share_pct"]))

    # 13 — declining products
    s, b = get("/api/dashboard/declining-products", {"supplier_id": nordic_id})
    results.append(check("GET /api/dashboard/declining-products", s, b, ["products", "comparison_days"]))

    # 14 — declining products custom window
    s, b = get("/api/dashboard/declining-products", {"supplier_id": nordic_id, "days": "60", "limit": "3"})
    results.append(check("GET /api/dashboard/declining-products (60d, limit=3)", s, b, ["products"]))

    # 15 — validation: bad supplier_id
    s, b = get("/api/dashboard/overview", {"supplier_id": "not-a-uuid"})
    ok = s == 422
    results.append(ok)
    print(f"{PASS if ok else FAIL} GET /api/dashboard/overview (bad supplier_id → 422)")

    # 16 — validation: bad granularity
    s, b = get("/api/dashboard/sales-over-time", {"supplier_id": nordic_id, "granularity": "year"})
    ok = s == 422
    results.append(ok)
    print(f"{PASS if ok else FAIL} GET /api/dashboard/sales-over-time (bad granularity → 422)")

    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{'─'*50}")
    print(f"API smoke test: {passed}/{total} passed")
    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
