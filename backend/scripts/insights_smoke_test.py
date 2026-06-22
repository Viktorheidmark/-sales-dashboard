"""
Phase 12 insights smoke test — 13 cases.

Tests save, list, read, export (JSON + CSV), cross-tenant isolation, and delete.
No actual LLM/MCP calls are made — insights are saved with synthetic payloads.

Requires the backend running on port 8000:
    cd backend && uvicorn app.main:app --reload

Run:
    python -m scripts.insights_smoke_test
"""

import csv
import io
import json
import sys

import httpx

BASE = "http://localhost:8000"
TIMEOUT = 15

NORDIC_EMAIL = "nordic@demo.solvigo"
SNACKS_EMAIL = "snacks@demo.solvigo"
PASSWORD = "demo1234"

# Synthetic chart payload — mirrors what chart_builder produces
SAMPLE_CHART = {
    "chart_type": "line_chart",
    "title": "Försäljningstrend 2026-03-23 → 2026-06-21",
    "description": "Intäkt per månad",
    "x_key": "label",
    "y_key": "revenue",
    "data": [
        {"label": "2026-03", "revenue": 12000.0},
        {"label": "2026-04", "revenue": 15000.0},
        {"label": "2026-05", "revenue": 13500.0},
    ],
    "source_tool": "get_sales_over_time",
    "generated_from_row_count": 3,
}


def login(email: str) -> tuple[dict, str]:
    r = httpx.post(
        f"{BASE}/api/auth/login",
        json={"email": email, "password": PASSWORD},
        timeout=TIMEOUT,
    )
    if r.status_code != 200:
        sys.exit(f"Login failed for {email} ({r.status_code}). Is server running with seed data?")
    return dict(r.cookies), r.json()["supplier_id"]


def check(label: str, assertions: list[tuple[str, bool]]) -> bool:
    all_ok = all(ok for _, ok in assertions)
    for desc, ok in assertions:
        print(f"  {'✓' if ok else '✗'} {desc}")
    print(f"{'✓' if all_ok else '✗'} {label}\n")
    return all_ok


def main():
    try:
        httpx.get(f"{BASE}/health", timeout=5).raise_for_status()
    except Exception:
        sys.exit(f"Cannot reach {BASE}. Start the backend first.")

    nordic_cookies, nordic_id = login(NORDIC_EMAIL)
    snacks_cookies, snacks_id = login(SNACKS_EMAIL)
    print(f"Nordic Coffee AB  → {nordic_id}")
    print(f"Fresh Snacks Ltd  → {snacks_id}\n")

    results: list[bool] = []
    saved_id: str = ""
    no_chart_id: str = ""

    # 1 — Login as Nordic Coffee (already done above)
    print("── Test 1: Login as Nordic Coffee ──")
    results.append(check("Login Nordic Coffee", [
        ("cookie present", bool(nordic_cookies.get("session"))),
        ("supplier_id non-empty", bool(nordic_id)),
    ]))

    # 2 — Save grounded insight with chart payload
    print("── Test 2: Save insight with chart ──")
    r = httpx.post(
        f"{BASE}/api/insights",
        json={
            "question": "Visa försäljningstrend de senaste 90 dagarna",
            "answer": "Vår omsättning under perioden var 40 500 kr fördelat på tre månader.",
            "chart": SAMPLE_CHART,
            "tool_calls": ["get_sales_over_time"],
            "sources": [{"tool": "get_sales_over_time", "source": "MCP:get_sales_over_time",
                          "supplier_id": nordic_id, "generated_at": "2026-06-22T10:00:00Z",
                          "row_count": 3, "date_range": {"start": "2026-03-23", "end": "2026-06-21"}}],
            "limitations": [],
        },
        cookies=nordic_cookies,
        timeout=TIMEOUT,
    )
    if r.status_code == 201:
        saved_id = r.json().get("id", "")
    results.append(check("Save insight with chart", [
        ("status 201", r.status_code == 201),
        ("id returned", bool(saved_id)),
        ("created_at returned", bool(r.json().get("created_at") if r.status_code == 201 else False)),
    ]))

    # 3 — List insights and verify saved insight appears
    print("── Test 3: List insights ──")
    r = httpx.get(f"{BASE}/api/insights", cookies=nordic_cookies, timeout=TIMEOUT)
    items = r.json() if r.status_code == 200 else []
    found = next((i for i in items if i.get("id") == saved_id), None)
    results.append(check("List insights — saved insight appears", [
        ("status 200", r.status_code == 200),
        ("saved insight in list", found is not None),
        ("has_chart is true", found.get("has_chart") is True if found else False),
        ("question matches", found.get("question", "").startswith("Visa försäljning") if found else False),
        ("source_tools listed", "get_sales_over_time" in found.get("source_tools", []) if found else False),
    ]))

    # 4 — Read full insight, verify content and supplier scope
    print("── Test 4: Read full insight ──")
    r = httpx.get(f"{BASE}/api/insights/{saved_id}", cookies=nordic_cookies, timeout=TIMEOUT)
    detail = r.json() if r.status_code == 200 else {}
    results.append(check("Read full insight — content and supplier scope", [
        ("status 200", r.status_code == 200),
        ("question matches", "försäljningstrend" in detail.get("question", "").lower()),
        ("answer non-empty", bool(detail.get("answer"))),
        ("chart present", detail.get("chart") is not None),
        ("chart_type is line_chart", detail.get("chart", {}).get("chart_type") == "line_chart"),
        ("tool_calls preserved", "get_sales_over_time" in detail.get("tool_calls", [])),
        ("no supplier_id leaked in response body",
         "supplier_id" not in str(detail.get("question", "")) + str(detail.get("answer", ""))),
    ]))

    # 5 — Export JSON — verify content type and no sensitive fields
    print("── Test 5: Export JSON ──")
    r = httpx.get(f"{BASE}/api/insights/{saved_id}/export.json", cookies=nordic_cookies, timeout=TIMEOUT)
    export_json = {}
    if r.status_code == 200:
        try:
            export_json = json.loads(r.content)
        except Exception:
            pass
    sources_in_export = export_json.get("sources", [])
    has_supplier_id_in_sources = any("supplier_id" in s for s in sources_in_export)
    results.append(check("Export JSON — correct content and no sensitive fields", [
        ("status 200", r.status_code == 200),
        ("content-type is application/json", "application/json" in r.headers.get("content-type", "")),
        ("content-disposition attachment", "attachment" in r.headers.get("content-disposition", "")),
        ("question present", "question" in export_json),
        ("answer present", "answer" in export_json),
        ("chart present", "chart" in export_json),
        ("supplier_id stripped from sources", not has_supplier_id_in_sources),
        ("no JWT or secret in export", "jwt" not in r.text.lower() and "secret" not in r.text.lower()),
    ]))

    # 6 — Export CSV — verify rows match chart data
    print("── Test 6: Export CSV ──")
    r = httpx.get(f"{BASE}/api/insights/{saved_id}/export.csv", cookies=nordic_cookies, timeout=TIMEOUT)
    csv_rows: list[dict] = []
    if r.status_code == 200:
        reader = csv.DictReader(io.StringIO(r.text))
        csv_rows = list(reader)
    results.append(check("Export CSV — chart rows as CSV", [
        ("status 200", r.status_code == 200),
        ("content-type is text/csv", "text/csv" in r.headers.get("content-type", "")),
        ("content-disposition attachment", "attachment" in r.headers.get("content-disposition", "")),
        ("3 data rows", len(csv_rows) == 3),
        ("label column present", all("label" in row for row in csv_rows)),
        ("revenue column present", all("revenue" in row for row in csv_rows)),
        ("first row matches", csv_rows[0].get("label") == "2026-03" if csv_rows else False),
    ]))

    # 7 — Save insight without chart
    print("── Test 7: Save insight without chart ──")
    r = httpx.post(
        f"{BASE}/api/insights",
        json={
            "question": "Vad är vår totala omsättning?",
            "answer": "Under perioden var omsättningen 52 000 kr.",
            "chart": None,
            "tool_calls": ["get_supplier_kpis"],
            "sources": [],
            "limitations": [],
        },
        cookies=nordic_cookies,
        timeout=TIMEOUT,
    )
    if r.status_code == 201:
        no_chart_id = r.json().get("id", "")
    results.append(check("Save insight without chart", [
        ("status 201", r.status_code == 201),
        ("id returned", bool(no_chart_id)),
    ]))

    # 8 — Export CSV for no-chart insight → 400
    print("── Test 8: Export CSV for no-chart insight → 400 ──")
    r = httpx.get(
        f"{BASE}/api/insights/{no_chart_id}/export.csv",
        cookies=nordic_cookies,
        timeout=TIMEOUT,
    )
    results.append(check("Export CSV no-chart → 400", [
        ("status 400", r.status_code == 400),
        ("detail message present", bool(r.json().get("detail") if r.status_code == 400 else False)),
    ]))

    # 9 — Login as Fresh Snacks
    print("── Test 9: Login as Fresh Snacks ──")
    results.append(check("Login Fresh Snacks", [
        ("cookie present", bool(snacks_cookies.get("session"))),
        ("different supplier_id", snacks_id != nordic_id),
    ]))

    # 10 — Verify Nordic insight NOT in Fresh Snacks list
    print("── Test 10: Nordic insight not in Fresh Snacks list ──")
    r = httpx.get(f"{BASE}/api/insights", cookies=snacks_cookies, timeout=TIMEOUT)
    snacks_ids = {i["id"] for i in r.json()} if r.status_code == 200 else set()
    results.append(check("Nordic insight not in Fresh Snacks list", [
        ("status 200", r.status_code == 200),
        ("nordic insight absent", saved_id not in snacks_ids),
    ]))

    # 11 — Verify Fresh Snacks cannot read, export, or delete Nordic insight → 404
    print("── Test 11: Cross-tenant access returns 404 ──")
    r_read = httpx.get(f"{BASE}/api/insights/{saved_id}", cookies=snacks_cookies, timeout=TIMEOUT)
    r_json = httpx.get(f"{BASE}/api/insights/{saved_id}/export.json", cookies=snacks_cookies, timeout=TIMEOUT)
    r_csv = httpx.get(f"{BASE}/api/insights/{saved_id}/export.csv", cookies=snacks_cookies, timeout=TIMEOUT)
    r_del = httpx.delete(f"{BASE}/api/insights/{saved_id}", cookies=snacks_cookies, timeout=TIMEOUT)
    results.append(check("Cross-tenant access → 404 (never 403 or 200)", [
        ("read → 404", r_read.status_code == 404),
        ("export JSON → 404", r_json.status_code == 404),
        ("export CSV → 404", r_csv.status_code == 404),
        ("delete → 404", r_del.status_code == 404),
    ]))

    # 12 — Delete Nordic insight as Nordic
    print("── Test 12: Delete insight ──")
    r = httpx.delete(f"{BASE}/api/insights/{saved_id}", cookies=nordic_cookies, timeout=TIMEOUT)
    results.append(check("Delete insight as owner → 204", [
        ("status 204", r.status_code == 204),
    ]))

    # 13 — Verify deleted insight no longer appears
    print("── Test 13: Deleted insight gone ──")
    r_list = httpx.get(f"{BASE}/api/insights", cookies=nordic_cookies, timeout=TIMEOUT)
    r_read = httpx.get(f"{BASE}/api/insights/{saved_id}", cookies=nordic_cookies, timeout=TIMEOUT)
    remaining_ids = {i["id"] for i in r_list.json()} if r_list.status_code == 200 else set()
    results.append(check("Deleted insight not in list, read → 404", [
        ("absent from list", saved_id not in remaining_ids),
        ("read returns 404", r_read.status_code == 404),
    ]))

    # Cleanup: delete no-chart insight
    httpx.delete(f"{BASE}/api/insights/{no_chart_id}", cookies=nordic_cookies, timeout=TIMEOUT)

    passed = sum(results)
    total = len(results)
    print(f"{'─' * 50}")
    print(f"Insights smoke test: {passed}/{total} passed")
    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
