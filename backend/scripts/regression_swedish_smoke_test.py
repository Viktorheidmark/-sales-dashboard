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
        "must_not_contain": ["Skånemejerier", "kund", "order", "ert märke"],
        "must_contain_supplier": True,
    },
    {
        "label": "Explicit Mejeri market share",
        "message": "Vad är vår marknadsandel i Mejeri?",
        "expected_tool": "get_market_share",
        "expect_chart": True,
        "chart_slices": {"Oss", "Konkurrenter"},
        "must_not_contain": ["Skånemejerier"],
        "must_contain_supplier": True,
        "direct_chart": True,
        "chart_type": "pie_chart",
    },
    {
        "label": "Regional sales ranking",
        "message": "Vilken region genererar mest intäkter?",
        "expected_tool": "get_sales_by_region",
        "expect_chart": True,
        "chart_slices": None,
        "must_not_contain": [],
        "must_contain_supplier": True,
        "direct_chart": True,
        "chart_type": "bar_chart",
    },
    {
        "label": "Top products in Stockholm",
        "message": "Vilka produkter säljer bäst i Stockholm?",
        "expected_tool": "get_top_products",
        "expect_chart": True,
        "chart_slices": None,
        "must_not_contain": ["marknadsföring", "överväg att fokusera"],
        "must_contain_supplier": False,
        "direct_chart": True,
        "chart_type": "bar_chart",
    },
    {
        "label": "Sales trend 30 days — complete weeks only",
        "message": "Hur har försäljningen utvecklats de senaste 30 dagarna?",
        "expected_tool": "get_sales_over_time",
        "expect_chart": True,
        "chart_slices": None,
        "must_not_contain": ["nedåtgående trend"],
        "must_contain_supplier": True,
        "weekly_complete_weeks": True,
        "direct_chart": True,
        "chart_type": "line_chart",
    },
    {
        "label": "Last completed week summary",
        "message": "Hur såg försäljningen ut senaste veckan?",
        "expected_tool": "get_sales_over_time",
        "expect_chart": True,
        "chart_type": "line_chart",
        "chart_slices": None,
        "must_not_contain": ["pågående vecka", "serien", "ofullständig", "exkluderats"],
        "must_contain": ["senaste avslutade vecka"],
        "must_contain_supplier": True,
        "weekly_completed_answer": True,
        "direct_chart": True,
        "widened_weekly_chart": True,
    },
    {
        "label": "Sales trend 90 days — incomplete period",
        "message": "Hur har försäljningen utvecklats de senaste 90 dagarna?",
        "expected_tool": "get_sales_over_time",
        "expect_chart": True,
        "chart_slices": None,
        "must_not_contain": ["intäktsförsäljning", "kraftig nedgång", "kraftigt fall"],
        "must_contain_supplier": True,
        "incomplete_period_safe": True,
    },
    {
        "label": "Focus next period — grounded advisory",
        "message": "Vad borde vi fokusera på nästa period?",
        "expected_tool": "get_declining_products",
        "expect_chart": True,
        "chart_slices": None,
        "must_not_contain": [],
        "must_contain_supplier": False,
        "grounded_advisory": True,
    },
    {
        "label": "Declining products — material decline prioritized",
        "message": "Vilken produkt minskade mest de senaste 30 dagarna?",
        "expected_tool": "get_declining_products",
        "expect_chart": True,
        "chart_slices": None,
        "must_not_contain": [],
        "must_contain_supplier": False,
        "declining_priority": True,
        "direct_chart": True,
        "chart_type": "bar_chart",
    },
]

PERIOD_FOLLOWUP_SCENARIOS = [
    {
        "label": "Sales trend → 30 days",
        "prior_message": "Hur såg försäljningen ut senaste veckan?",
        "followup_message": "senaste 30 dagarna då?",
        "expected_tool": "get_sales_over_time",
        "chart_type": "line_chart",
    },
    {
        "label": "Market share → 30 days",
        "prior_message": "Vad är vår marknadsandel i Mejeri?",
        "followup_message": "senaste 30 dagarna då?",
        "expected_tool": "get_market_share",
        "chart_type": "pie_chart",
    },
    {
        "label": "Top products Stockholm → 30 days",
        "prior_message": "Vilka produkter säljer bäst i Stockholm?",
        "followup_message": "senaste 30 dagarna då?",
        "expected_tool": "get_top_products",
        "chart_type": "bar_chart",
        "expect_region": "Stockholm",
    },
]

FOLLOWUP_SCENARIOS = [
    {
        "label": "Diagram after market share",
        "prior_message": "Vad är vår marknadsandel i Mejeri?",
        "expected_tool": "get_market_share",
        "expect_chart": True,
        "chart_type": "pie_chart",
    },
    {
        "label": "Diagram after Stockholm top products",
        "prior_message": "Vilka produkter säljer bäst i Stockholm?",
        "expected_tool": "get_top_products",
        "expect_chart": True,
        "chart_type": "bar_chart",
    },
    {
        "label": "Diagram after declining product",
        "prior_message": "Vilken produkt minskade mest de senaste 30 dagarna?",
        "expected_tool": "get_declining_products",
        "expect_chart": True,
        "chart_type": "bar_chart",
    },
    {
        "label": "Diagram after weekly sales trend",
        "prior_message": "Hur såg försäljningen ut senaste veckan?",
        "followup_message": "visa diagram",
        "expected_tool": "get_sales_over_time",
        "expect_chart": False,
        "redundant_diagram": True,
    },
    {
        "label": "Diagram after period comparison",
        "prior_message": "Hur ser försäljningen ut jämfört med föregående period?",
        "expected_tool": "get_sales_over_time",
        "expect_chart": True,
        "chart_type": "line_chart",
    },
]

PLANNING_PHRASES = [
    "jag kommer att",
    "jag ska hämta",
    "kommer att kontrollera",
]

UNSUPPORTED_RECOMMENDATION_RE = re.compile(
    r"(stärka marknadsföringen|sänk priset|lagerproblem|"
    r"öka marknadsföringsbudgeten|satsa mer på marknadsföring|"
    r"kundpreferenser|överväg strategier|prissättning|"
    r"marknadsföringsinsatser|lageroptimering|"
    r"överväg att fokusera på marknadsföring|"
    r"överväg att analysera|"
    r"analysera specifika produktprestationer|vidta strategier|"
    r"kampanj|distribution|lageråtgärd|prisändring|"
    r"tillväxtmöjligheter|framgångsfaktorer|tillväxtområden|"
    r"identifiera potentiella)",
    re.IGNORECASE,
)

FORBIDDEN_MARKET_SHARE_PHRASES = ("en aktör", "dominerar marknaden", "representeras av")

SUPPLIER_PRODUCT_CONCAT_RE = re.compile(
    r"arla sverige\s+(iced|mellanmjölk|standardmjölk|keso)",
    re.IGNORECASE,
)


def _has_unsupported_recommendation(answer: str) -> bool:
    return bool(UNSUPPORTED_RECOMMENDATION_RE.search(answer))


def _misnames_product(answer: str) -> bool:
    return bool(SUPPLIER_PRODUCT_CONCAT_RE.search(answer))


DECIMAL_HEAVY_CURRENCY = re.compile(r"\d{2,}\s\d{3}[,\.]\d")


def _currency_formatter_examples() -> bool:
    from app.services.currency_format import format_compact_sek

    return (
        format_compact_sek(75619) == "75,6 tkr"
        and format_compact_sek(52358.6) == "52,4 tkr"
        and format_compact_sek(971.1) == "971 kr"
        and format_compact_sek(1200000) == "1,2 mkr"
    )


def _no_mislabeled_tkr_as_mkr(answer: str) -> bool:
    """Catch tkr-scale amounts wrongly shown as mkr (e.g. 75,6 mkr for 75 619 SEK)."""
    return not bool(re.search(r"(?<!\d)(\d{1,2},\d)\s*mkr", answer, re.IGNORECASE))


def login(email: str) -> tuple[dict, str, str]:
    r = httpx.post(
        f"{BASE}/api/auth/login",
        json={"email": email, "password": "demo1234"},
        timeout=10,
    )
    if r.status_code != 200:
        sys.exit(f"Login failed: HTTP {r.status_code}")
    body = r.json()
    return dict(r.cookies), body["supplier_id"], body.get("supplier_name", "")


def chat(cookies: dict, message: str, prior_context: dict | None = None) -> dict:
    body: dict = {"message": message}
    if prior_context:
        body["prior_context"] = prior_context
    r = httpx.post(
        f"{BASE}/api/chat",
        json=body,
        cookies=cookies,
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def consume_stream(cookies: dict, message: str, prior_context: dict | None = None) -> list[dict]:
    body: dict = {"message": message}
    if prior_context:
        body["prior_context"] = prior_context
    events: list[dict] = []
    buf = ""
    with httpx.stream(
        "POST",
        f"{BASE}/api/chat/stream",
        json=body,
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


def _chart_first_last_labels(chart: dict | None) -> tuple[str | None, str | None]:
    data = (chart or {}).get("data") or []
    if not data:
        return None, None
    return str(data[0].get("label", ""))[:10], str(data[-1].get("label", ""))[:10]


def _source_matches_chart_range(result: dict) -> bool:
    chart = result.get("chart")
    sources = result.get("sources", [])
    if not chart or not sources:
        return True
    dr = sources[0].get("date_range")
    first, last = _chart_first_last_labels(chart)
    if not dr or not first:
        return True
    if dr.get("start", "")[:10] != first:
        return False
    if last:
        from datetime import date, timedelta
        last_sunday = (date.fromisoformat(last) + timedelta(days=6)).isoformat()
        if dr.get("end", "")[:10] != last_sunday:
            return False
    return True


def _weekly_complete_weeks_only(result: dict) -> bool:
    from datetime import date
    from app.services.period_utils import completed_week_bounds

    chart = result.get("chart")
    sources = result.get("sources", [])
    if not chart or not sources:
        return True
    dr = sources[0].get("date_range")
    if not dr:
        return True
    start = date.fromisoformat(dr["start"][:10])
    if start.weekday() != 0:
        return False
    end = date.fromisoformat(dr["end"][:10])
    _, completed_end = completed_week_bounds()
    if end > completed_end:
        return False
    first, _ = _chart_first_last_labels(chart)
    if first and first < dr["start"][:10]:
        return False
    return _source_matches_chart_range(result)


def _widened_chart_labeled(result: dict) -> bool:
    chart = result.get("chart") or {}
    combined = f"{chart.get('title', '')} {chart.get('description', '')}".lower()
    return "utveckling inför" in combined and "avslutade veckor" in combined


def _weekly_completed_answer_safe(result: dict, answer: str) -> bool:
    lower = answer.lower()
    if "senaste avslutade vecka" not in lower:
        return False
    if any(tok in lower for tok in ["pågående vecka", "serien", "ofullständig", "exkluderats"]):
        return False
    limitations = " ".join(result.get("limitations", [])).lower()
    if any(tok in limitations for tok in ["pågående", "serien", "jämförelseperiod", "ofullständig"]):
        return False
    return True


def _incomplete_period_safe(result: dict, answer: str) -> bool:
    lower = answer.lower()
    chart = result.get("chart") or {}
    period_note = chart.get("period_note") or ""

    if period_note:
        if any(tok in lower for tok in ["pågående", "ofullständig", "exkluderats"]):
            return False
        return True

    if "senaste avslutade vecka" in lower:
        if any(tok in lower for tok in ["pågående vecka", "ofullständig", "exkluderats"]):
            return False
        return True

    limitations = " ".join(result.get("limitations", [])).lower()
    sources_lim = " ".join(
        lim
        for s in result.get("sources", [])
        for lim in (s.get("limitations") or [])
    ).lower()
    combined = f"{lower} {limitations} {sources_lim}"
    if any(tok in combined for tok in ["pågående", "ofullständig", "exkluderats"]):
        return True
    if any(tok in lower for tok in ["kraftig nedgång", "kraftigt fall", "stort fall"]):
        return False
    return True


def _chart_labels_readable(chart: dict | None) -> bool:
    if not chart:
        return True
    if chart.get("layout") != "horizontal":
        return False
    if chart.get("tooltip_key") != "product_name":
        return False
    for row in chart.get("data", []):
        if not row.get("product_name"):
            return False
    return True


def _declining_prioritizes_material(chart: dict | None) -> bool:
    if not chart or chart.get("source_tool") != "get_declining_products":
        return True
    rows = chart.get("data") or []
    if not rows:
        return False
    first = rows[0].get("revenue_change_pct")
    if first is None:
        return True
    return float(first) <= -5.0


def assert_case(
    label: str,
    result: dict,
    spec: dict,
    supplier_id: str,
    supplier_name: str = "",
) -> bool:
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

    if spec.get("chart_slices"):
        checks.append((
            "chart has expected slices",
            spec["chart_slices"].issubset(chart_names),
        ))

    for forbidden in spec.get("must_not_contain", []):
        checks.append((f"no '{forbidden}'", forbidden.lower() not in lower))

    for required in spec.get("must_contain", []):
        checks.append((f"contains '{required}'", required.lower() in lower))

    if spec.get("must_contain_supplier") and supplier_name:
        checks.append((
            f"uses supplier name ({supplier_name})",
            supplier_name.lower() in lower,
        ))

    if spec.get("grounded_advisory"):
        pass  # covered by global unsupported recommendation check

    if spec.get("declining_priority") or spec.get("grounded_advisory"):
        checks.append(("product names not prefixed with supplier", not _misnames_product(answer)))

    if spec["expected_tool"] == "get_top_products":
        checks.append(("product names not prefixed with supplier", not _misnames_product(answer)))

    if spec.get("incomplete_period_safe"):
        checks.append(("incomplete period handled safely", _incomplete_period_safe(result, answer)))
        if chart and chart.get("period_note"):
            checks.append(("period note on chart", True))
            checks.append((
                "no duplicate incomplete warning in answer",
                not any(tok in lower for tok in ["pågående", "ofullständig", "exkluderats"]),
            ))

    if spec.get("weekly_complete_weeks"):
        checks.append(("complete weeks only", _weekly_complete_weeks_only(result)))
        checks.append(("source matches chart range", _source_matches_chart_range(result)))

    if spec.get("weekly_completed_answer"):
        checks.append(("weekly completed answer safe", _weekly_completed_answer_safe(result, answer)))
        checks.append((
            "no incomplete-period limitation shown",
            not any(
                tok in " ".join(result.get("limitations", [])).lower()
                for tok in ["pågående", "serien", "jämförelseperiod"]
            ),
        ))

    if spec.get("direct_chart"):
        checks.append(("direct chart on first answer", chart is not None))
        checks.append((
            "chart source tool matches",
            chart is not None and chart.get("source_tool") == spec["expected_tool"],
        ))

    if spec.get("chart_type"):
        checks.append((
            "expected chart type",
            chart is not None and chart.get("chart_type") == spec["chart_type"],
        ))

    if spec.get("widened_weekly_chart"):
        checks.append(("widened weekly chart labeled", _widened_chart_labeled(result)))
        checks.append(("source matches chart range", _source_matches_chart_range(result)))

    if spec.get("declining_priority"):
        checks.append(("declining chart prioritizes material drop", _declining_prioritizes_material(chart)))
        if chart:
            checks.append(("declining chart horizontal", chart.get("layout") == "horizontal"))

    if spec["expected_tool"] == "get_market_share":
        checks.append((
            "answer mentions share/percentage or Mejeri",
            any(tok in lower for tok in ["%", "procent", "andel", "mejeri"]),
        ))
        for phrase in FORBIDDEN_MARKET_SHARE_PHRASES:
            checks.append((f"no '{phrase}'", phrase not in lower))

    if spec["expected_tool"] == "get_top_products" and chart:
        checks.append(("top products chart readable labels", _chart_labels_readable(chart)))

    checks.append((
        "no decimal-heavy currency formatting",
        not bool(DECIMAL_HEAVY_CURRENCY.search(answer)),
    ))

    checks.append(("no unsupported generic recommendations", not _has_unsupported_recommendation(answer)))
    checks.append(("no mislabeled tkr as mkr", _no_mislabeled_tkr_as_mkr(answer)))

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


def assert_period_followup(
    label: str,
    result: dict,
    spec: dict,
    supplier_id: str,
) -> bool:
    chart = result.get("chart")
    checks = [
        ("answer non-empty", bool(result.get("answer", "").strip())),
        ("expected tool called", spec["expected_tool"] in result.get("tool_calls", [])),
        ("not wrong market-share tool",
         spec["expected_tool"] == "get_market_share" or "get_market_share" not in result.get("tool_calls", [])),
        ("chart present", chart is not None),
        ("supplier scope preserved", result.get("supplier_id") == supplier_id),
    ]
    if spec.get("chart_type"):
        checks.append(("expected chart type", chart and chart.get("chart_type") == spec["chart_type"]))
    if spec["expected_tool"] == "get_market_share":
        checks.append(("chart is market share", chart is None or chart.get("source_tool") == "get_market_share"))
    if spec["expected_tool"] == "get_sales_over_time":
        checks.append(("chart is sales trend", chart is None or chart.get("source_tool") == "get_sales_over_time"))

    all_ok = True
    for desc, ok in checks:
        print(f"  {PASS if ok else FAIL} {desc}")
        if not ok:
            all_ok = False
    marker = PASS if all_ok else FAIL
    print(f"{marker} {label}")
    if result.get("answer"):
        preview = result["answer"][:180].replace("\n", " ")
        print(f"     Answer: {preview}{'…' if len(result['answer']) > 180 else ''}")
    return all_ok


def assert_followup(
    label: str,
    result: dict,
    spec: dict,
    supplier_id: str,
) -> bool:
    chart = result.get("chart")
    checks = [
        ("answer non-empty", bool(result.get("answer", "").strip())),
        ("expected tool called", spec["expected_tool"] in result.get("tool_calls", [])),
        ("chart present", chart is not None),
        ("supplier scope preserved", result.get("supplier_id") == supplier_id),
    ]
    if spec.get("chart_type"):
        checks.append(("expected chart type", chart and chart.get("chart_type") == spec["chart_type"]))
    if spec.get("widened_chart"):
        checks.append(("widened chart labeled", _widened_chart_labeled(result)))
        checks.append(("source matches chart range", _source_matches_chart_range(result)))
    if spec.get("redundant_diagram"):
        checks.append(("no duplicate chart", chart is None))
        checks.append(("no tool re-fetch", len(result.get("tool_calls", [])) == 0))
        checks.append((
            "redundant diagram message",
            "redan ovan" in result.get("answer", "").lower(),
        ))
    if spec["expected_tool"] == "get_market_share":
        checks.append(("not generic sales trend only", chart is None or chart.get("source_tool") == "get_market_share"))

    all_ok = True
    for desc, ok in checks:
        print(f"  {PASS if ok else FAIL} {desc}")
        if not ok:
            all_ok = False
    marker = PASS if all_ok else FAIL
    print(f"{marker} {label}")
    return all_ok


def main():
    try:
        httpx.get(f"{BASE}/health", timeout=5).raise_for_status()
    except Exception:
        sys.exit(f"Cannot reach {BASE}. Start server: cd backend && uvicorn app.main:app --reload")

    cookies, supplier_id, supplier_name = login("arla@demo.solvigo")
    print(f"\n{supplier_name} → {supplier_id}\n")

    print("── Currency formatter unit checks ──")
    formatter_ok = _currency_formatter_examples()
    print(f"  {PASS if formatter_ok else FAIL} compact SEK examples (tkr/mkr)")
    results = [formatter_ok]

    for spec in REGRESSION_QUESTIONS:
        print(f"── Non-streaming: {spec['label']} ──")
        result = chat(cookies, spec["message"])
        results.append(assert_case(
            f"POST /api/chat — {spec['label']}", result, spec, supplier_id, supplier_name,
        ))

        print(f"\n── Streaming: {spec['label']} ──")
        events = consume_stream(cookies, spec["message"])
        stream_result = complete_from_stream(events)
        has_complete = "complete" in [e["type"] for e in events]
        has_delta = "delta" in [e["type"] for e in events]
        print(f"  {PASS if has_complete else FAIL} complete event received")
        print(f"  {PASS if has_delta else FAIL} delta events received")
        results.append(has_complete and has_delta)
        results.append(assert_case(
            f"POST /api/chat/stream — {spec['label']}", stream_result, spec, supplier_id, supplier_name,
        ))

    for scenario in PERIOD_FOLLOWUP_SCENARIOS:
        print(f"\n── Period follow-up: {scenario['label']} ──")
        prior = chat(cookies, scenario["prior_message"])
        prior_context = {
            "question": scenario["prior_message"],
            "answer": prior.get("answer", ""),
            "tool_calls": prior.get("tool_calls", []),
            "sources": prior.get("sources", []),
            "has_chart": prior.get("chart") is not None,
        }
        followup = chat(cookies, scenario["followup_message"], prior_context)
        results.append(assert_period_followup(
            f"Period follow-up — {scenario['label']}", followup, scenario, supplier_id,
        ))

    for scenario in FOLLOWUP_SCENARIOS:
        print(f"\n── Follow-up: {scenario['label']} ──")
        prior = chat(cookies, scenario["prior_message"])
        prior_context = {
            "question": scenario["prior_message"],
            "answer": prior.get("answer", ""),
            "tool_calls": prior.get("tool_calls", []),
            "sources": prior.get("sources", []),
            "has_chart": prior.get("chart") is not None,
        }
        followup = chat(
            cookies,
            scenario.get("followup_message", "Visa ett diagram för det."),
            prior_context,
        )
        results.append(assert_followup(
            f"Follow-up diagram — {scenario['label']}", followup, scenario, supplier_id,
        ))

    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{'─' * 50}")
    print(f"Regression Swedish smoke test: {passed}/{total} passed")
    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
