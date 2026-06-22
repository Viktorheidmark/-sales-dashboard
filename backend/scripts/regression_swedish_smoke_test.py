"""
Regression smoke tests for Swedish analytics questions.

Requires the FastAPI server:
    cd backend && uvicorn app.main:app --reload

Run:
    python -m scripts.regression_swedish_smoke_test
"""

import json
import re
import sys

try:
    import httpx
except ImportError:
    sys.exit("httpx not installed. Run: pip install httpx")

BASE = "http://localhost:8000"
PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
TIMEOUT = 120

REGRESSION_QUESTIONS = [
    {
        "label": "Brand vs competitors (default Mejeri)",
        "message": "Hur går det för vårt märke jämfört med konkurrenterna?",
        "expected_tool": "get_market_share",
        "expect_chart": True,
        "chart_slices": {"Oss", "Konkurrenter"},
        "must_not_contain": ["Skånemejerier", "kund", "order"],
    },
    {
        "label": "Explicit Mejeri market share",
        "message": "Vad är vår marknadsandel i Mejeri?",
        "expected_tool": "get_market_share",
        "expect_chart": True,
        "chart_slices": {"Oss", "Konkurrenter"},
        "must_not_contain": ["Skånemejerier"],
    },
    {
        "label": "Top products in Stockholm",
        "message": "Vilka produkter säljer bäst i Stockholm?",
        "expected_tool": "get_top_products",
        "expect_chart": True,
        "chart_slices": None,
        "must_not_contain": [],
    },
]

PLANNING_PHRASES = [
    "jag kommer att",
    "jag ska hämta",
    "kommer att kontrollera",
]


def login(email: str) -> tuple[dict, str]:
    r = httpx.post(
        f"{BASE}/api/auth/login",
        json={"email": email, "password": "demo1234"},
        timeout=10,
    )
    if r.status_code != 200:
        sys.exit(f"Login failed: HTTP {r.status_code}")
    return dict(r.cookies), r.json()["supplier_id"]


def chat(cookies: dict, message: str) -> dict:
    r = httpx.post(
        f"{BASE}/api/chat",
        json={"message": message},
        cookies=cookies,
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def consume_stream(cookies: dict, message: str) -> list[dict]:
    events: list[dict] = []
    buf = ""
    with httpx.stream(
        "POST",
        f"{BASE}/api/chat/stream",
        json={"message": message},
        cookies=cookies,
        timeout=TIMEOUT,
        headers={"Accept": "text/event-stream"},
    ) as r:
        r.raise_for_status()
        for raw_chunk in r.iter_text():
            buf += raw_chunk
            blocks = buf.split("\n\n")
            buf = blocks.pop()
            for block in blocks:
                block = block.strip()
                if not block:
                    continue
                event_type = ""
                data_str = ""
                for line in block.split("\n"):
                    if line.startswith("event: "):
                        event_type = line[7:].strip()
                    elif line.startswith("data: "):
                        data_str = line[6:].strip()
                if data_str:
                    events.append({"type": event_type, "data": json.loads(data_str)})
    return events


def complete_from_stream(events: list[dict]) -> dict:
    for e in events:
        if e["type"] == "complete":
            return e["data"]
    return {}


def assert_case(label: str, result: dict, spec: dict, supplier_id: str) -> bool:
    answer = result.get("answer", "")
    lower = answer.lower()
    chart = result.get("chart")
    chart_data = chart.get("data", []) if chart else []
    chart_names = {row.get("name") for row in chart_data if isinstance(row, dict)}

    checks = [
        ("answer non-empty", bool(answer.strip())),
        ("not planning-only answer", not any(p in lower for p in PLANNING_PHRASES)),
        ("expected tool called", spec["expected_tool"] in result.get("tool_calls", [])),
        ("sources present", len(result.get("sources", [])) > 0),
        ("supplier scope preserved", result.get("supplier_id") == supplier_id),
        (
            "chart present when applicable",
            (chart is not None) if spec["expect_chart"] else True,
        ),
    ]

    if spec["chart_slices"]:
        checks.append((
            "chart has expected slices",
            spec["chart_slices"].issubset(chart_names),
        ))

    for forbidden in spec["must_not_contain"]:
        checks.append((f"no leak '{forbidden}'", forbidden.lower() not in lower))

    if spec["expected_tool"] == "get_market_share":
        checks.append((
            "answer mentions share/percentage or Mejeri",
            any(tok in lower for tok in ["%", "procent", "andel", "mejeri"]),
        ))

    all_ok = True
    for desc, ok in checks:
        print(f"  {PASS if ok else FAIL} {desc}")
        if not ok:
            all_ok = False
    marker = PASS if all_ok else FAIL
    print(f"{marker} {label}")
    if answer:
        preview = answer[:180].replace("\n", " ")
        print(f"     Answer: {preview}{'…' if len(answer) > 180 else ''}")
    return all_ok


def main():
    try:
        httpx.get(f"{BASE}/health", timeout=5).raise_for_status()
    except Exception:
        sys.exit(f"Cannot reach {BASE}. Start server: cd backend && uvicorn app.main:app --reload")

    cookies, supplier_id = login("arla@demo.solvigo")
    print(f"\nArla Sverige → {supplier_id}\n")

    results = []

    for spec in REGRESSION_QUESTIONS:
        print(f"── Non-streaming: {spec['label']} ──")
        result = chat(cookies, spec["message"])
        results.append(assert_case(f"POST /api/chat — {spec['label']}", result, spec, supplier_id))

        print(f"\n── Streaming: {spec['label']} ──")
        events = consume_stream(cookies, spec["message"])
        stream_result = complete_from_stream(events)
        has_complete = "complete" in [e["type"] for e in events]
        has_delta = "delta" in [e["type"] for e in events]
        print(f"  {PASS if has_complete else FAIL} complete event received")
        print(f"  {PASS if has_delta else FAIL} delta events received")
        results.append(has_complete and has_delta)
        results.append(assert_case(f"POST /api/chat/stream — {spec['label']}", stream_result, spec, supplier_id))

    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{'─' * 50}")
    print(f"Regression Swedish smoke test: {passed}/{total} passed")
    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
