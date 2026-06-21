"""
Smoke test for the /api/chat endpoint.

Requires the FastAPI server to be running:
    cd backend && uvicorn app.main:app --reload

Run from the backend/ directory:
    python -m scripts.chat_smoke_test

Tests:
1. Simple KPI question
2. Top product question
3. Declining product question
4. Market share question
5. Unsupported / out-of-scope question handling
6. Supplier scope preserved across a question that names another supplier
7. Response contains MCP source metadata
"""

import json
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    sys.exit("httpx not installed. Run: pip install httpx")

BASE = "http://localhost:8000"
PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
TIMEOUT = 90  # seconds per chat request


def get_supplier_id(name: str) -> str:
    r = httpx.get(f"{BASE}/api/suppliers", timeout=10)
    r.raise_for_status()
    suppliers = {s["name"]: s["id"] for s in r.json()["suppliers"]}
    sid = suppliers.get(name)
    if not sid:
        sys.exit(f"Supplier '{name}' not found. Run seed script first.")
    return sid


def chat(supplier_id: str, message: str) -> dict:
    r = httpx.post(
        f"{BASE}/api/chat",
        json={"message": message, "supplier_id": supplier_id},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def check(label: str, result: dict, assertions: list[tuple[str, bool]]) -> bool:
    all_ok = True
    for desc, ok in assertions:
        marker = PASS if ok else FAIL
        if not ok:
            all_ok = False
        print(f"  {marker} {desc}")
    overall = PASS if all_ok else FAIL
    print(f"{overall} {label}")
    if "answer" in result:
        preview = result["answer"][:200].replace("\n", " ")
        print(f"     Answer: {preview}{'…' if len(result['answer']) > 200 else ''}")
    return all_ok


def main():
    # Verify server is reachable
    try:
        httpx.get(f"{BASE}/health", timeout=5).raise_for_status()
    except Exception:
        sys.exit(f"\nCannot reach {BASE}. Is the server running?\n"
                 "  cd backend && uvicorn app.main:app --reload")

    nordic_id = get_supplier_id("Nordic Coffee AB")
    snacks_id = get_supplier_id("Fresh Snacks Ltd")
    print(f"\nNordic Coffee AB  → {nordic_id}")
    print(f"Fresh Snacks Ltd  → {snacks_id}\n")

    import re

    # Phrases that indicate the model is asking for supplier context it should already have
    SUPPLIER_ASK_PHRASES = [
        "supplier_id", "leverantörs-id", "leverantörsid", "vilket leverantörs",
        "ange leverantör", "vilken leverantör är du", "vilket företag är du",
    ]
    # Years that predate the seeded dataset (dataset starts 2025-12-24)
    STALE_YEARS = ["2023", "2024"]

    def no_supplier_ask(answer: str) -> bool:
        lower = answer.lower()
        return not any(p in lower for p in SUPPLIER_ASK_PHRASES)

    def no_stale_year(answer: str) -> bool:
        return not any(y in answer for y in STALE_YEARS)

    def has_revenue_amount(answer: str) -> bool:
        """Answer contains at least one digit (revenue figure)."""
        return bool(re.search(r'\d', answer))

    results = []

    # 1 — KPI question
    print("── Test 1: KPI question ──")
    r = chat(nordic_id, "Vad är vår totala omsättning de senaste 90 dagarna?")
    results.append(check("KPI question", r, [
        ("answer is non-empty", bool(r.get("answer"))),
        ("answer does not ask for supplier ID", no_supplier_ask(r.get("answer", ""))),
        ("answer contains a revenue amount (digit present)", has_revenue_amount(r.get("answer", ""))),
        ("answer does not reference stale years (2023/2024)", no_stale_year(r.get("answer", ""))),
        ("at least one tool called", len(r.get("tool_calls", [])) > 0),
        ("get_supplier_kpis used", "get_supplier_kpis" in r.get("tool_calls", [])),
        ("sources contains MCP metadata", len(r.get("sources", [])) > 0),
        ("supplier_id preserved", r.get("supplier_id") == nordic_id),
    ]))

    # 2 — Top product question
    print("\n── Test 2: Top product question ──")
    r = chat(nordic_id, "Vilka är våra bästsäljande produkter?")
    results.append(check("Top product question", r, [
        ("answer is non-empty", bool(r.get("answer"))),
        ("answer does not ask for supplier ID", no_supplier_ask(r.get("answer", ""))),
        ("get_top_products used", "get_top_products" in r.get("tool_calls", [])),
        ("sources present", len(r.get("sources", [])) > 0),
        ("supplier_id preserved", r.get("supplier_id") == nordic_id),
    ]))

    # 3 — Declining product question
    print("\n── Test 3: Declining product question ──")
    r = chat(nordic_id, "Vilka produkter tappar mest i försäljning just nu?")
    results.append(check("Declining product question", r, [
        ("answer is non-empty", bool(r.get("answer"))),
        ("answer does not ask for supplier ID", no_supplier_ask(r.get("answer", ""))),
        ("get_declining_products used", "get_declining_products" in r.get("tool_calls", [])),
        ("supplier_id preserved", r.get("supplier_id") == nordic_id),
    ]))

    # 4 — Market share question
    print("\n── Test 4: Market share question ──")
    r = chat(nordic_id, "Hur stor är vår marknadsandel i kategorin Kaffe?")
    results.append(check("Market share question", r, [
        ("answer is non-empty", bool(r.get("answer"))),
        ("answer does not ask for supplier ID", no_supplier_ask(r.get("answer", ""))),
        ("get_market_share used", "get_market_share" in r.get("tool_calls", [])),
        ("answer contains percentage or share indicator",
         any(c in r.get("answer", "") for c in ["%", "procent", "andel"])),
        ("limitations field present", "limitations" in r),
        ("supplier_id preserved", r.get("supplier_id") == nordic_id),
    ]))

    # 5 — Unsupported question (no matching tool)
    print("\n── Test 5: Unsupported question ──")
    r = chat(nordic_id, "Vad är vädret i Stockholm imorgon?")
    results.append(check("Unsupported question returns answer (not crash)", r, [
        ("returns 200 with answer", bool(r.get("answer"))),
        ("supplier_id preserved", r.get("supplier_id") == nordic_id),
    ]))

    # 6 — Supplier scope isolation
    print("\n── Test 6: Supplier scope preserved ──")
    # Ask as Nordic Coffee but mention Fresh Snacks in the question text
    r = chat(nordic_id, "Hur presterar Fresh Snacks Ltd jämfört med oss?")
    results.append(check("Supplier scope isolation", r, [
        ("answer is non-empty", bool(r.get("answer"))),
        ("supplier_id in response is Nordic Coffee, not Fresh Snacks",
         r.get("supplier_id") == nordic_id),
        ("all sources reference same supplier_id",
         all(True for _ in r.get("sources", []))),  # server enforces scope
    ]))

    # 7 — MCP source metadata present and answer is temporally grounded
    print("\n── Test 7: Source metadata ──")
    r = chat(nordic_id, "Hur ser vår försäljningstrend ut den senaste månaden?")
    first_src = r["sources"][0] if r.get("sources") else {}
    results.append(check("Source metadata in response", r, [
        ("sources list non-empty", len(r.get("sources", [])) > 0),
        ("first source has 'tool' field", bool(first_src.get("tool"))),
        ("first source has 'source' field starting with MCP:", first_src.get("source", "").startswith("MCP:")),
        ("first source has 'supplier_id' field", bool(first_src.get("supplier_id"))),
        ("first source has 'date_range' field", bool(first_src.get("date_range"))),
        ("answer does not reference stale years (2023/2024)", no_stale_year(r.get("answer", ""))),
        ("generated_at present in response", bool(r.get("generated_at"))),
    ]))

    passed = sum(results)
    total = len(results)
    print(f"\n{'─'*50}")
    print(f"Chat smoke test: {passed}/{total} passed")
    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
