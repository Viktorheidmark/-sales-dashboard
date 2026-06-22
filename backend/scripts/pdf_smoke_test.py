"""
Phase 13 PDF smoke test — 8 cases.

Tests: PDF export with chart, PDF export without chart, cross-tenant 404,
after-delete 404, and frontend source scan for removed JSON/CSV exports.

No actual LLM/MCP calls — insights are saved with synthetic payloads.

Requires the backend running on port 8000:
    cd backend && uvicorn app.main:app --reload

Run:
    python -m scripts.pdf_smoke_test
"""

import sys
from pathlib import Path

import httpx

BASE = "http://localhost:8000"
TIMEOUT = 30  # PDF generation can be slow on first call (matplotlib init)

NORDIC_EMAIL = "arla@demo.solvigo"
SNACKS_EMAIL = "orkla@demo.solvigo"
PASSWORD = "demo1234"

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
    print(f"Arla Sverige  → {nordic_id}")
    print(f"Orkla Sverige  → {snacks_id}\n")

    results: list[bool] = []
    chart_insight_id = ""
    no_chart_insight_id = ""

    # 1 — Login as Arla Sverige
    print("── Test 1: Login as Arla Sverige ──")
    results.append(check("Login Arla Sverige", [
        ("cookie present", bool(nordic_cookies.get("session"))),
        ("supplier_id non-empty", bool(nordic_id)),
    ]))

    # 2 — Save insight with chart
    print("── Test 2: Save insight with chart ──")
    r = httpx.post(
        f"{BASE}/api/insights",
        json={
            "question": "Visa vår försäljningstrend de senaste 90 dagarna",
            "answer": "Vår omsättning under perioden var 40 500 kr fördelat på tre månader.",
            "chart": SAMPLE_CHART,
            "tool_calls": ["get_sales_over_time"],
            "sources": [{"tool": "get_sales_over_time", "row_count": 3}],
            "limitations": ["Exkluderar returer"],
        },
        cookies=nordic_cookies,
        timeout=TIMEOUT,
    )
    if r.status_code == 201:
        chart_insight_id = r.json().get("id", "")
    results.append(check("Save insight with chart", [
        ("status 201", r.status_code == 201),
        ("id returned", bool(chart_insight_id)),
    ]))

    # 3 — Export PDF with chart → 200, correct content-type, valid PDF bytes
    print("── Test 3: Export PDF with chart ──")
    r = httpx.get(
        f"{BASE}/api/insights/{chart_insight_id}/export.pdf",
        cookies=nordic_cookies,
        timeout=TIMEOUT,
    )
    is_pdf_header = r.content[:4] == b"%PDF" if r.status_code == 200 else False
    results.append(check("Export PDF with chart — valid PDF bytes", [
        ("status 200", r.status_code == 200),
        ("content-type application/pdf", "application/pdf" in r.headers.get("content-type", "")),
        ("content-disposition attachment", "attachment" in r.headers.get("content-disposition", "")),
        ("filename ends with .pdf", r.headers.get("content-disposition", "").endswith(".pdf\"")),
        ("starts with %PDF magic bytes", is_pdf_header),
        ("non-trivial size > 10 KB", len(r.content) > 10_000 if r.status_code == 200 else False),
    ]))

    # 4 — Save insight WITHOUT chart
    print("── Test 4: Save insight without chart ──")
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
        no_chart_insight_id = r.json().get("id", "")
    results.append(check("Save insight without chart", [
        ("status 201", r.status_code == 201),
        ("id returned", bool(no_chart_insight_id)),
    ]))

    # 5 — Export PDF without chart still returns 200 (chart block is omitted gracefully)
    print("── Test 5: Export PDF without chart → still 200 ──")
    r = httpx.get(
        f"{BASE}/api/insights/{no_chart_insight_id}/export.pdf",
        cookies=nordic_cookies,
        timeout=TIMEOUT,
    )
    is_pdf_header = r.content[:4] == b"%PDF" if r.status_code == 200 else False
    results.append(check("Export PDF no chart — 200 with valid PDF", [
        ("status 200", r.status_code == 200),
        ("application/pdf content-type", "application/pdf" in r.headers.get("content-type", "")),
        ("valid PDF magic bytes", is_pdf_header),
        ("size > 1 KB", len(r.content) > 1_000 if r.status_code == 200 else False),
    ]))

    # 6 — Cross-tenant: Orkla cannot export Arla insight
    print("── Test 6: Cross-tenant PDF export → 404 ──")
    r = httpx.get(
        f"{BASE}/api/insights/{chart_insight_id}/export.pdf",
        cookies=snacks_cookies,
        timeout=TIMEOUT,
    )
    results.append(check("Cross-tenant PDF export → 404 (never 403)", [
        ("status 404", r.status_code == 404),
    ]))

    # 7 — Delete insight, then verify PDF → 404
    print("── Test 7: PDF export after delete → 404 ──")
    del_r = httpx.delete(
        f"{BASE}/api/insights/{chart_insight_id}",
        cookies=nordic_cookies,
        timeout=TIMEOUT,
    )
    r = httpx.get(
        f"{BASE}/api/insights/{chart_insight_id}/export.pdf",
        cookies=nordic_cookies,
        timeout=TIMEOUT,
    )
    results.append(check("PDF export after delete → 404", [
        ("delete → 204", del_r.status_code == 204),
        ("PDF → 404", r.status_code == 404),
    ]))

    # 8 — Frontend source scan: JSON/CSV export buttons must be gone from InsightsPanel
    print("── Test 8: Frontend source scan — no JSON/CSV export in InsightsPanel ──")
    panel_path = Path(__file__).resolve().parent.parent.parent / "frontend/src/components/sections/InsightsPanel.tsx"
    panel_src = panel_path.read_text() if panel_path.exists() else ""
    results.append(check("InsightsPanel has no JSON/CSV export, has PDF export", [
        ("file exists", panel_path.exists()),
        ("no 'Export JSON' text", "Export JSON" not in panel_src),
        ("no exportInsightJson call", "exportInsightJson" not in panel_src),
        ("no exportInsightCsv call", "exportInsightCsv" not in panel_src),
        ("exportInsightPdf present", "exportInsightPdf" in panel_src),
        ("PDF button text present", "Exportera rapport som PDF" in panel_src),
    ]))

    # Cleanup
    if no_chart_insight_id:
        httpx.delete(f"{BASE}/api/insights/{no_chart_insight_id}", cookies=nordic_cookies, timeout=TIMEOUT)

    passed = sum(results)
    total = len(results)
    print(f"{'─' * 50}")
    print(f"PDF smoke test: {passed}/{total} passed")
    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
