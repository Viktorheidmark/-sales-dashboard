"""
API smoke test for the Solvigo dashboard endpoints.

Requires the FastAPI server to be running:
    cd backend && uvicorn app.main:app --reload

Run from the backend/ directory:
    python -m scripts.api_smoke_test

Logs in as Nordic Coffee AB and Fresh Snacks Ltd demo accounts,
then hits every dashboard endpoint and reports pass/fail.
"""

import sys
import json

try:
    import httpx
except ImportError:
    sys.exit("httpx not installed. Run: pip install httpx")

BASE = "http://localhost:8000"
PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"


def login(email: str) -> tuple[dict, str]:
    """Log in and return (cookies, supplier_id)."""
    r = httpx.post(
        f"{BASE}/api/auth/login",
        json={"email": email, "password": "demo1234"},
        timeout=10,
    )
    if r.status_code != 200:
        sys.exit(f"Login failed for {email}: HTTP {r.status_code} — run seed script first.")
    return dict(r.cookies), r.json()["supplier_id"]


def get(path: str, cookies: dict, params: dict = None) -> tuple[int, dict]:
    r = httpx.get(f"{BASE}{path}", params=params or {}, cookies=cookies, timeout=10)
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
    try:
        httpx.get(f"{BASE}/health", timeout=5).raise_for_status()
    except Exception:
        sys.exit(f"\nCould not reach {BASE}. Is the server running?\n"
                 "  cd backend && uvicorn app.main:app --reload")

    nordic_cookies, nordic_id = login("nordic@demo.solvigo")
    snacks_cookies, snacks_id = login("snacks@demo.solvigo")
    clean_cookies, clean_id = login("home@demo.solvigo")

    print(f"\nNordic Coffee AB  →  {nordic_id}")
    print(f"Fresh Snacks Ltd  →  {snacks_id}\n")

    results = []

    # 1 — /health (public)
    s, b = get("/health", cookies={})
    results.append(check("GET /health", s, b, ["status"]))

    # 2 — /api/auth/me
    s, b = get("/api/auth/me", cookies=nordic_cookies)
    results.append(check("GET /api/auth/me", s, b, ["supplier_id", "supplier_name", "email"]))

    # 3 — overview
    s, b = get("/api/dashboard/overview", nordic_cookies)
    results.append(check("GET /api/dashboard/overview", s, b,
                         ["total_revenue", "total_orders", "total_units", "date_range"]))

    # 4 — overview with date range
    s, b = get("/api/dashboard/overview", nordic_cookies,
               {"start_date": "2026-01-01", "end_date": "2026-03-31"})
    results.append(check("GET /api/dashboard/overview (date range)", s, b, ["total_revenue"]))

    # 5 — sales-over-time monthly
    s, b = get("/api/dashboard/sales-over-time", nordic_cookies, {"granularity": "month"})
    results.append(check("GET /api/dashboard/sales-over-time (monthly)", s, b, ["series", "granularity"]))

    # 6 — sales-over-time weekly
    s, b = get("/api/dashboard/sales-over-time", nordic_cookies, {"granularity": "week"})
    results.append(check("GET /api/dashboard/sales-over-time (weekly)", s, b, ["series"]))

    # 7 — top-products default
    s, b = get("/api/dashboard/top-products", nordic_cookies)
    results.append(check("GET /api/dashboard/top-products (default)", s, b, ["products"]))

    # 8 — top-products filtered by region
    s, b = get("/api/dashboard/top-products", nordic_cookies,
               {"region": "Stockholm", "limit": "3"})
    results.append(check("GET /api/dashboard/top-products (Stockholm, limit=3)", s, b,
                         ["products", "region_filter"]))

    # 9 — regions (Nordic)
    s, b = get("/api/dashboard/regions", nordic_cookies)
    results.append(check("GET /api/dashboard/regions", s, b, ["regions"]))

    # 10 — regions for Fresh Snacks (Malmö pattern)
    s, b = get("/api/dashboard/regions", snacks_cookies)
    results.append(check("GET /api/dashboard/regions (Fresh Snacks)", s, b, ["regions"]))

    # 11 — market-share Coffee
    s, b = get("/api/dashboard/market-share", nordic_cookies, {"category_name": "Coffee"})
    results.append(check("GET /api/dashboard/market-share (Coffee)", s, b,
                         ["market_share_pct", "supplier_revenue", "category_total_revenue"]))

    # 12 — market-share Household
    s, b = get("/api/dashboard/market-share", clean_cookies, {"category_name": "Household"})
    results.append(check("GET /api/dashboard/market-share (Household)", s, b, ["market_share_pct"]))

    # 13 — declining products
    s, b = get("/api/dashboard/declining-products", nordic_cookies)
    results.append(check("GET /api/dashboard/declining-products", s, b, ["products", "comparison_days"]))

    # 14 — declining products custom window
    s, b = get("/api/dashboard/declining-products", nordic_cookies, {"days": "60", "limit": "3"})
    results.append(check("GET /api/dashboard/declining-products (60d, limit=3)", s, b, ["products"]))

    # 15 — unauthenticated request → 401
    s, b = get("/api/dashboard/overview", cookies={})
    ok = s == 401
    results.append(ok)
    print(f"{PASS if ok else FAIL} GET /api/dashboard/overview (no cookie → 401)")

    # 16 — validation: bad granularity
    s, b = get("/api/dashboard/sales-over-time", nordic_cookies, {"granularity": "year"})
    ok = s == 422
    results.append(ok)
    print(f"{PASS if ok else FAIL} GET /api/dashboard/sales-over-time (bad granularity → 422)")

    # 17 — data-status: basic shape
    s, b = get("/api/dashboard/data-status", nordic_cookies)
    results.append(check("GET /api/dashboard/data-status (Nordic)", s, b,
                         ["supplier_id", "period_start", "period_end", "latest_order_date",
                          "total_orders", "total_units", "generated_at"]))

    # 18 — data-status: supplier scope isolation
    s_n, n = get("/api/dashboard/data-status", nordic_cookies)
    s_f, f = get("/api/dashboard/data-status", snacks_cookies)
    ok = (s_n == 200 and s_f == 200
          and n.get("supplier_id") == nordic_id
          and f.get("supplier_id") == snacks_id
          and n.get("total_orders") != f.get("total_orders"))
    results.append(ok)
    print(f"{PASS if ok else FAIL} data-status supplier_id isolation (Nordic ≠ Fresh Snacks)")

    # 19 — data-status: non-negative counts and valid date format
    ok = (s_n == 200
          and n.get("total_orders", -1) >= 0
          and n.get("total_units", -1) >= 0
          and isinstance(n.get("latest_order_date"), str)
          and len(n.get("latest_order_date", "")) == 10)  # YYYY-MM-DD
    results.append(ok)
    print(f"{PASS if ok else FAIL} data-status counts non-negative, latest_order_date is YYYY-MM-DD")

    # 20 — data-status: unauthenticated → 401
    s, b = get("/api/dashboard/data-status", cookies={})
    ok = s == 401
    results.append(ok)
    print(f"{PASS if ok else FAIL} GET /api/dashboard/data-status (no cookie → 401)")

    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{'─'*50}")
    print(f"API smoke test: {passed}/{total} passed")
    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
