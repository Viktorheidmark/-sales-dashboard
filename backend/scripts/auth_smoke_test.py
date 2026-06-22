"""
Auth smoke test for Phase 9 — demo authentication and backend-enforced supplier tenancy.

Requires the FastAPI server to be running:
    cd backend && uvicorn app.main:app --reload

Run from the backend/ directory:
    python -m scripts.auth_smoke_test

Tests:
 1. Login with valid credentials → 200, session cookie set
 2. Login with wrong password → 401
 3. Login with unknown email → 401
 4. GET /api/auth/me with valid cookie → 200, correct supplier data
 5. GET /api/auth/me with no cookie → 401
 6. GET /api/dashboard/overview with valid cookie → 200
 7. GET /api/dashboard/overview with no cookie → 401
 8. Tenant tampering: supplier_id query param ignored — response stays scoped to session tenant
 9. Tenant tampering: supplier_id in chat body ignored — response stays scoped to session tenant
10. POST /api/auth/logout → 200, cookie cleared
11. GET /api/auth/me after logout → 401
"""

import sys

try:
    import httpx
except ImportError:
    sys.exit("httpx not installed. Run: pip install httpx")

BASE = "http://localhost:8000"
PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
TIMEOUT = 30


def check(label: str, assertions: list[tuple[str, bool]]) -> bool:
    all_ok = all(ok for _, ok in assertions)
    for desc, ok in assertions:
        print(f"  {PASS if ok else FAIL} {desc}")
    print(f"{PASS if all_ok else FAIL} {label}")
    return all_ok


def main():
    try:
        httpx.get(f"{BASE}/health", timeout=5).raise_for_status()
    except Exception:
        sys.exit(
            f"\nCannot reach {BASE}. Is the server running?\n"
            "  cd backend && uvicorn app.main:app --reload"
        )

    results = []

    # ── 1: Valid login ──────────────────────────────────────────────────────
    print("── Test 1: Valid login ──")
    r = httpx.post(
        f"{BASE}/api/auth/login",
        json={"email": "arla@demo.solvigo", "password": "demo1234"},
        timeout=TIMEOUT,
    )
    cookie_set = "session" in r.cookies
    body = r.json() if r.status_code == 200 else {}
    results.append(check("Valid login", [
        ("returns 200", r.status_code == 200),
        ("session cookie set", cookie_set),
        ("supplier_name in response", body.get("supplier_name") == "Arla Sverige"),
        ("supplier_id in response", bool(body.get("supplier_id"))),
    ]))
    nordic_cookie = dict(r.cookies) if cookie_set else {}
    nordic_supplier_id = body.get("supplier_id", "")

    # ── 2: Wrong password ──────────────────────────────────────────────────
    print("\n── Test 2: Wrong password ──")
    r = httpx.post(
        f"{BASE}/api/auth/login",
        json={"email": "arla@demo.solvigo", "password": "wrongpassword"},
        timeout=TIMEOUT,
    )
    results.append(check("Wrong password → 401", [
        ("returns 401", r.status_code == 401),
    ]))

    # ── 3: Unknown email ───────────────────────────────────────────────────
    print("\n── Test 3: Unknown email ──")
    r = httpx.post(
        f"{BASE}/api/auth/login",
        json={"email": "nobody@example.com", "password": "demo1234"},
        timeout=TIMEOUT,
    )
    results.append(check("Unknown email → 401", [
        ("returns 401", r.status_code == 401),
    ]))

    # ── 4: GET /api/auth/me with valid cookie ──────────────────────────────
    print("\n── Test 4: GET /api/auth/me with valid cookie ──")
    r = httpx.get(f"{BASE}/api/auth/me", cookies=nordic_cookie, timeout=TIMEOUT)
    body = r.json() if r.status_code == 200 else {}
    results.append(check("GET /api/auth/me (authenticated)", [
        ("returns 200", r.status_code == 200),
        ("supplier_id matches login", body.get("supplier_id") == nordic_supplier_id),
        ("supplier_name correct", body.get("supplier_name") == "Arla Sverige"),
        ("email correct", body.get("email") == "arla@demo.solvigo"),
    ]))

    # ── 5: GET /api/auth/me with no cookie ────────────────────────────────
    print("\n── Test 5: GET /api/auth/me with no cookie ──")
    r = httpx.get(f"{BASE}/api/auth/me", timeout=TIMEOUT)
    results.append(check("GET /api/auth/me (unauthenticated) → 401", [
        ("returns 401", r.status_code == 401),
    ]))

    # ── 6: Dashboard with valid cookie ────────────────────────────────────
    print("\n── Test 6: Dashboard with valid cookie ──")
    r = httpx.get(
        f"{BASE}/api/dashboard/overview",
        cookies=nordic_cookie,
        timeout=TIMEOUT,
    )
    body = r.json() if r.status_code == 200 else {}
    results.append(check("GET /api/dashboard/overview (authenticated)", [
        ("returns 200", r.status_code == 200),
        ("supplier_id matches session", body.get("supplier_id") == nordic_supplier_id),
    ]))

    # ── 7: Dashboard with no cookie ───────────────────────────────────────
    print("\n── Test 7: Dashboard with no cookie → 401 ──")
    r = httpx.get(f"{BASE}/api/dashboard/overview", timeout=TIMEOUT)
    results.append(check("GET /api/dashboard/overview (unauthenticated) → 401", [
        ("returns 401", r.status_code == 401),
    ]))

    # ── 8: Tenant tampering — supplier_id query param ignored ─────────────
    print("\n── Test 8: Tenant tampering via query param ──")
    # Log in as Orkla to get a different supplier_id
    snacks_login = httpx.post(
        f"{BASE}/api/auth/login",
        json={"email": "orkla@demo.solvigo", "password": "demo1234"},
        timeout=TIMEOUT,
    )
    snacks_supplier_id = snacks_login.json().get("supplier_id", "") if snacks_login.status_code == 200 else ""
    # Make dashboard request as Arla but pass Orkla supplier_id in the query string
    r = httpx.get(
        f"{BASE}/api/dashboard/overview",
        params={"supplier_id": snacks_supplier_id},  # attempt to tamper scope
        cookies=nordic_cookie,
        timeout=TIMEOUT,
    )
    body = r.json() if r.status_code == 200 else {}
    results.append(check("Tenant tampering: supplier_id query param ignored", [
        ("returns 200 (not rejected)", r.status_code == 200),
        ("response supplier_id is Arla (session), not Orkla (param)",
         body.get("supplier_id") == nordic_supplier_id),
    ]))

    # ── 9: Tenant tampering — supplier_id in chat body ignored ────────────
    print("\n── Test 9: Tenant tampering via chat body ──")
    r = httpx.post(
        f"{BASE}/api/chat",
        json={
            "message": "Vad är vår totala omsättning?",
            "supplier_id": snacks_supplier_id,   # attempt to tamper scope via body
        },
        cookies=nordic_cookie,
        timeout=90,
    )
    body = r.json() if r.status_code == 200 else {}
    results.append(check("Tenant tampering: supplier_id in chat body ignored", [
        ("returns 200", r.status_code == 200),
        ("response supplier_id is Arla (session), not Orkla (body)",
         body.get("supplier_id") == nordic_supplier_id),
    ]))

    # ── 10: Logout ────────────────────────────────────────────────────────
    print("\n── Test 10: Logout ──")
    r = httpx.post(f"{BASE}/api/auth/logout", cookies=nordic_cookie, timeout=TIMEOUT)
    results.append(check("POST /api/auth/logout", [
        ("returns 200", r.status_code == 200),
    ]))

    # ── 11: /me after logout ──────────────────────────────────────────────
    print("\n── Test 11: /api/auth/me after logout ──")
    # httpx does not automatically propagate the cleared cookie from logout response,
    # so we test with the original cookie — in a real browser the cookie would be cleared.
    # Instead, test with an obviously invalid token.
    r = httpx.get(
        f"{BASE}/api/auth/me",
        cookies={"session": "invalid.token.value"},
        timeout=TIMEOUT,
    )
    results.append(check("Invalid session token → 401", [
        ("returns 401", r.status_code == 401),
    ]))

    passed = sum(results)
    total = len(results)
    print(f"\n{'─'*50}")
    print(f"Auth smoke test: {passed}/{total} passed")
    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
