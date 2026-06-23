"""
Focused regression for direct weekly chart date alignment.

Run:
    cd backend && python -m scripts.weekly_chart_regression
"""

import sys

try:
    import httpx
except ImportError:
    sys.exit("httpx not installed")

from datetime import date, timedelta

from app.services.period_utils import completed_week_bounds

BASE = "http://localhost:8000"
TIMEOUT = 120
PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"


def login() -> dict:
    r = httpx.post(
        f"{BASE}/api/auth/login",
        json={"email": "arla@demo.solvigo", "password": "demo1234"},
        timeout=10,
    )
    r.raise_for_status()
    return dict(r.cookies)


def chart_last_sunday(chart: dict) -> str | None:
    data = chart.get("data") or []
    if not data:
        return None
    last_monday = str(data[-1].get("label", ""))[:10]
    if not last_monday:
        return None
    return (date.fromisoformat(last_monday) + timedelta(days=6)).isoformat()


def main() -> None:
    try:
        httpx.get(f"{BASE}/health", timeout=5).raise_for_status()
    except Exception:
        sys.exit(f"Cannot reach {BASE}. Start server first.")

    _, expected_end = completed_week_bounds()
    expected_end_s = expected_end.isoformat()
    second_last_monday = (expected_end - timedelta(days=13)).isoformat()

    cookies = login()
    r = httpx.post(
        f"{BASE}/api/chat",
        json={"message": "Hur såg försäljningen ut senaste veckan?"},
        cookies=cookies,
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    body = r.json()

    answer = body.get("answer", "")
    chart = body.get("chart") or {}
    sources = body.get("sources") or []
    source_end = (sources[0].get("date_range") or {}).get("end") if sources else None
    last_sunday = chart_last_sunday(chart)
    data = chart.get("data") or []

    checks = [
        ("chart present", chart is not None and len(data) >= 2),
        ("answer mentions completed week end", expected_end_s[5:10].replace("-0", "-") in answer or str(expected_end.day) in answer),
        (f"chart final week ends {expected_end_s}", last_sunday == expected_end_s),
        (f"source range ends {expected_end_s}", source_end == expected_end_s),
        ("8–14 / second-to-last is not final", len(data) >= 2 and str(data[-2].get("label", ""))[:10] == second_last_monday),
        (
            "chart note matches completed Sunday",
            chart.get("period_note") == chart.get("description")
            and expected_end_s[8:10].lstrip("0") in (chart.get("description") or ""),
        ),
    ]

    all_ok = True
    print("\n── Direct weekly chart date regression ──")
    for desc, ok in checks:
        print(f"  {PASS if ok else FAIL} {desc}")
        if not ok:
            all_ok = False

    print(f"\n  Answer ends with: …{answer[-80:]}")
    print(f"  Chart last label: {data[-1].get('label') if data else 'n/a'}")
    print(f"  Source end: {source_end}")
    print(f"  Chart description: {chart.get('description')}")

    if not all_ok:
        sys.exit(1)
    print(f"\n{PASS} All checks passed")


if __name__ == "__main__":
    main()
