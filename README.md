# Solvigo Sales Intelligence

A supplier-facing AI sales dashboard. Suppliers log in and see how their products perform across regions, time periods, and categories — and can ask natural-language questions answered by a grounded AI copilot.

Built as a developer-case MVP demonstrating MCP-based LLM grounding, supplier scope isolation, and controlled competitor data exposure.

---

## Problem solved

Retailers own all sales data. Suppliers historically had no self-serve analytics — they relied on slow, expensive reporting cycles. This dashboard gives each supplier a live window into their own performance without exposing competitor order-level detail or other suppliers' data.

The AI copilot is grounded through the Model Context Protocol (MCP): the LLM calls structured analytics tools rather than generating SQL or reasoning from memory. Every quantitative claim in a chat answer is backed by a real tool result.

---

## Architecture

```mermaid
graph LR
    A[React / Vite<br/>frontend] -->|REST JSON| B[FastAPI<br/>backend]
    B -->|OpenAI tool-calling loop| C[OpenAI API<br/>gpt-4o]
    C -->|tool call| B
    B -->|MCP stdio transport| D[FastMCP server<br/>mcp_server/]
    D -->|parameterised SQL<br/>SQLAlchemy| E[(Neon PostgreSQL)]
    B -->|direct import<br/>dashboard endpoints only| D
```

**Request flow for the AI copilot:**

```
ChatPanel (React)
  → POST /api/chat   (FastAPI locks supplier_id)
  → app/services/chat.py
  → OpenAI tool-calling loop (max 5 rounds)
  → MCP stdio transport  ← supplier_id injected here, LLM never sees it
  → mcp_server/server.py
  → query_helpers.py  (parameterised SQL, supplier-scoped)
  → Neon PostgreSQL
  → structured JSON result → Swedish answer + optional chart payload
```

---

## Why MCP

The Model Context Protocol lets the backend expose typed, supplier-scoped analytics tools that the LLM calls by name — `get_supplier_kpis`, `get_top_products`, etc. This means:

- The LLM never generates SQL or touches the database directly.
- The backend injects `supplier_id` into every tool call after the LLM decides which tool to call. The model cannot choose or override it.
- Tool schemas presented to the LLM have `supplier_id` stripped — the model never even sees the field.
- Competitor data is enforced aggregate-only inside each tool query, regardless of what the LLM requests.

Dashboard endpoints (non-chat) call the same `query_helpers` functions directly for performance — only the chat flow uses MCP stdio transport.

---

## Saved insights and PDF reports

Authenticated supplier users can save any grounded chat answer (one backed by MCP tool data) and later retrieve or export it as a polished PDF report.

**Behaviour:**
- Insights are supplier-scoped — the backend derives `supplier_id` from the session cookie; the frontend never sends it.
- Cross-tenant reads, exports, or deletes always return 404 (never 403).
- Only grounded responses (those with `tool_calls.length > 0`) can be saved — guardrail, unsupported, or clarification responses have no "Save insight" button.
- The chart payload is stored as JSONB and reproduced faithfully on export; chart values always come from MCP results, never from AI prose.
- PDF is the only user-facing export format — no public sharing links or bulk operations in this MVP.

**PDF report format (A4):**
- Header band: slate-900 background, "◈ Solvigo Sales Intelligence" (brand blue), supplier name (right), "Analysrapport" sub-label.
- Body: fråga (question), analys (answer text, line-by-line), chart rendered as PNG via matplotlib (line/bar/pie), datakällor (source tools as human-readable Swedish labels), begränsningar (limitations in amber).
- Footer: "Baserat på MCP-analytiklagret · Inte simulerade data · Solvigo Sales Intelligence" + generation timestamp.
- Chart render uses brand palette (`#4169e1`, `#a5b4fc`, `#c7d2fe`). Negative bar values (e.g. declining %) get `#ef4444`. Chart block is silently omitted if no chart was saved.
- No `supplier_id`, JWT, database URLs, or internal paths appear in the output.

**Endpoints (all require session cookie):**

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/insights` | Save a grounded insight |
| `GET` | `/api/insights` | List own insights (newest first, max 100) |
| `GET` | `/api/insights/{id}` | Full detail including chart |
| `DELETE` | `/api/insights/{id}` | Delete own insight |
| `GET` | `/api/insights/{id}/export.pdf` | Download polished A4 PDF report |

PDF generation: `backend/app/services/pdf_builder.py` — `reportlab` (Platypus, A4) + `matplotlib` (Agg backend, in-memory PNG). No browser or system-level dependencies.

Smoke test: `python -m scripts.pdf_smoke_test` (8 cases, requires running backend).

---

## Chat charts

Each grounded chat answer can include a deterministic chart payload rendered directly in the chat UI.

| MCP tool | Chart type | x-axis | y-axis |
|---|---|---|---|
| `get_sales_over_time` | line | period (YYYY-MM or date) | revenue |
| `get_top_products` | bar | product name | revenue |
| `get_sales_by_region` | bar | region | revenue |
| `get_market_share` | pie | "Oss" / "Konkurrenter" | revenue |
| `get_declining_products` | bar | product name | % change |
| `get_supplier_kpis` | — | no chart | — |

**Key properties:**
- Charts are built by `backend/app/services/chart_builder.py` from raw MCP output — the LLM response text is never parsed for numbers.
- At most one chart is returned per answer. When multiple MCP tools are called, the chart comes from the highest-priority visual tool (trend → market share → top products → region → declining).
- A chart is suppressed when the MCP result has fewer than two usable rows.
- All guardrail responses (`prompt_injection`, `restricted`, `insufficient_data`, `unsupported`, `clarification_needed`) always return `chart = null`.
- Chart data inherits the authenticated supplier's scope — supplier\_id is injected by the backend before every MCP call.
- The frontend renders charts with Recharts, reusing the same library as the dashboard.

Chart payload structure:

```json
{
  "chart_type": "line_chart | bar_chart | pie_chart",
  "title": "Försäljningstrend 2026-03-23 → 2026-06-21",
  "description": "Intäkt per månad",
  "x_key": "label",
  "y_key": "revenue",
  "data": [{ "label": "2026-03", "revenue": 12345.67 }],
  "source_tool": "get_sales_over_time",
  "generated_from_row_count": 12
}
```

Smoke test: `python -m scripts.chart_smoke_test` (9 cases, requires running backend).

---

## Guardrails and safety

Every chat message is classified **deterministically** before any OpenAI or MCP call is made. The guardrail layer in `backend/app/services/guardrails.py` uses regex pattern matching — no LLM involved — and returns immediately for non-analytics inputs.

| Classification | Trigger examples | Action |
|---|---|---|
| `prompt_injection` | "ignore previous instructions", "reveal the system prompt", "run SQL", "what is the JWT secret" | Refuse; return Swedish error; no LLM/MCP |
| `restricted` | "which customers do competitors have?", "show competitor orders" | Explain aggregate-only policy; no LLM/MCP |
| `insufficient_data` | margin, profit, inventory, returns, forecasts, ad spend | Explain what data is available; no LLM/MCP |
| `unsupported` | weather, sports, coding, news, stock prices | Redirect to analytics; no LLM/MCP |
| `clarification_needed` | vague questions with no analytics signal ("how's it going?") | Ask follow-up with 4 suggested directions |
| `supported` | sales, revenue, products, trends, regions, market share | Pass through to full LLM + MCP flow |

**Security invariants (enforced in layers):**
- The guardrail never exposes: JWT contents, JWT secret, environment variables, database URLs, raw SQL, internal system prompts, MCP implementation details, server paths, or source code.
- `supplier_id` is derived exclusively from the authenticated session — not from the message, not from the LLM.
- The MCP tool list is whitelisted in `ALLOWED_TOOLS`; the LLM cannot add or modify tools.
- Tool arguments are schema-validated; `supplier_id` is overwritten by the backend immediately before every MCP call.
- Competitor data remains aggregate-only at both the guardrail layer (pattern match) and the MCP query layer (SQL enforced).

Smoke test: `python backend/scripts/guardrail_smoke_test.py` (13 cases, requires running backend).

---

## Supplier scope and competitor guardrails

| Concern | Enforcement point |
|---|---|
| LLM choosing wrong supplier | `supplier_id` stripped from OpenAI schema; backend always overwrites |
| Cross-supplier data leakage | All queries join through `brands.supplier_id` |
| Competitor product/order detail | `query_market_share` returns aggregate revenue only; no product names or order rows |
| SQL injection | All queries use SQLAlchemy `text()` with named bind params |

---

## Grounding and source metadata

Every chat response includes:

```json
{
  "tool_calls": ["get_supplier_kpis"],
  "sources": [{
    "tool": "get_supplier_kpis",
    "source": "MCP:get_supplier_kpis",
    "supplier_id": "...",
    "generated_at": "2026-06-21T14:32:00Z",
    "date_range": { "start": "2026-03-23", "end": "2026-06-21" },
    "row_count": 1,
    "limitations": []
  }],
  "limitations": [],
  "supplier_id": "...",
  "generated_at": "2026-06-21T14:32:01Z"
}
```

The system prompt injects today's date at call time and instructs the model to quote the `date_range` returned by the tool — not to infer calendar periods from its training data.

---

## Data model

```
Supplier → Brand → Product ← Category
                       ↓
Customer ← Region   OrderItem
    ↓                  ↑
  Order ──────────────┘

Supplier → SavedInsight
```

UUID primary keys throughout. `OrderItem` stores `quantity`, `unit_price`, and pre-computed `revenue`. `SavedInsight` is scaffolded but not used in the MVP UI.

---

## Demo suppliers

| Supplier | Key pattern |
|---|---|
| **Nordic Coffee AB** | Highest Stockholm revenue; upward trend last 90 days; Cold Brew declining |
| **Fresh Snacks Ltd** | Relatively stronger in Malmö |
| **Clean Home Co** | Stable lower-growth across all regions |
| **Baltic Roasters AB** | Coffee competitor (~35% Coffee share); cross-sells Nordic Coffee SKUs |

---

## Local setup

### Prerequisites

- Python 3.11+
- Node 18+
- A Neon PostgreSQL database (or any PostgreSQL 14+)
- An OpenAI API key with access to `gpt-4o`

### 1 — Environment

```bash
# Copy and fill in root .env (used by backend and MCP server)
cp .env.example .env
# Edit DATABASE_URL and OPENAI_API_KEY
```

Root `.env` format:

```
DATABASE_URL=postgresql+psycopg://user:password@host:5432/dbname
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
```

> **Note:** Use the `postgresql+psycopg://` scheme (sync psycopg driver). `asyncpg` is not used.

```bash
# Frontend environment (defaults work for local dev)
cp frontend/.env.example frontend/.env
```

### 2 — Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Seed demo data (~2 000 orders across 4 suppliers)
python -m scripts.seed_demo_data

# Start API server
uvicorn app.main:app --reload      # http://localhost:8000
```

### 3 — Frontend

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

### 4 — MCP server (standalone, optional)

The MCP server runs as a subprocess of the FastAPI backend automatically. To inspect it standalone:

```bash
# From project root, with backend/.venv active
python -m mcp_server.server        # stdio transport
fastmcp dev mcp_server/server.py   # browser inspector (requires fastmcp CLI)
```

---

## Demo flow

A suggested walkthrough for a live evaluator demo. Takes approximately 5 minutes.

1. **Log in as Nordic Coffee AB** — open `http://localhost:5173`, click the "Nordic Coffee AB" demo account card, then click "Logga in". The dashboard loads with KPIs, trend, top products, regions, market share, and declining products for the last 90 days.

2. **Inspect the dashboard** — note that "Omsättning" (revenue), region rankings, and "Marknadsandel" (market share) panels all update from live MCP data. Change the date range to "30 dagar" and observe all panels refresh. The green live-data indicator confirms real database queries.

3. **Ask a grounded trend question** — scroll to "Analytics Copilot" and type or click:
   > *Hur ser vår försäljningstrend ut den senaste månaden?*
   The copilot calls `get_sales_over_time` via MCP (the "Hämtar data via MCP…" indicator appears), then returns a Swedish answer with a deterministic line chart. The chart is built from raw tool output — never from AI prose.

4. **Ask a guarded competitor question** — type:
   > *Vilka produkter säljer våra konkurrenter?*
   The guardrail intercepts this deterministically (no OpenAI call is made) and returns a Swedish explanation of the aggregate-only competitor policy.

5. **Save a chart insight** — on the grounded trend answer (which has the "via" source badges), click "Spara insikt". The button shows "✓ Sparad" when saved. Click "☆ Insikter" in the header to open the insights drawer and confirm the saved entry appears.

6. **Export a PDF report** — open the saved insight and click "↓ Exportera rapport som PDF". A polished A4 PDF downloads with the branded header, answer text, embedded chart, and data sources. The PDF is generated server-side from the saved chart payload — not from AI text.

7. **Demonstrate tenant isolation** — click "Logga ut", then log in as "Fresh Snacks Ltd". Confirm that the dashboard shows different KPIs and that the "☆ Insikter" drawer is empty (Nordic Coffee's insights are not visible).

---

## Verification commands

All smoke tests require the backend to be running (`uvicorn app.main:app --reload`) unless noted.

```bash
# MCP query layer — no server needed, runs against DB directly
cd /path/to/project
source backend/.venv/bin/activate
python -m mcp_server.smoke_test

# Dashboard API endpoints
cd backend
python -m scripts.api_smoke_test

# AI chat grounding (slower — each test calls OpenAI)
cd backend
python -m scripts.chat_smoke_test
```

Expected results when demo data is seeded:

```
MCP smoke test:   6/6 passed
API smoke test:  16/16 passed
Chat smoke test:  7/7 passed
```

### Frontend build

```bash
cd frontend
npm run build
```

---

## Interactive API docs

With the backend running: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Suggested demo questions (Swedish)

Ask these in the Analytics Copilot panel as Nordic Coffee AB:

```
Vad är vår totala omsättning de senaste 90 dagarna?
Vilka är våra bästsäljande produkter?
Vilka produkter tappar mest i försäljning just nu?
Hur stor är vår marknadsandel i kategorin Kaffe?
Hur ser vår försäljningstrend ut den senaste månaden?
Vilka är våra bästsäljande produkter i Stockholm?
Hur presterar vi i Göteborg jämfört med Stockholm?
```

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Service health |
| `GET` | `/api/suppliers` | List suppliers (id + name) |
| `GET` | `/api/dashboard/overview` | KPIs: revenue, orders, units, AOV |
| `GET` | `/api/dashboard/sales-over-time` | Time series (day / week / month) |
| `GET` | `/api/dashboard/top-products` | Top products by revenue, optional region filter |
| `GET` | `/api/dashboard/regions` | Revenue by region |
| `GET` | `/api/dashboard/market-share` | Supplier share within a category |
| `GET` | `/api/dashboard/declining-products` | Products declining vs prior period |
| `POST` | `/api/chat` | Grounded AI chat |

---

## Tradeoffs and known limitations

| Area | Current approach | Alternative |
|---|---|---|
| Auth | None (demo only) | Auth0 / Supabase Auth per supplier |
| MCP transport | stdio subprocess per chat request | HTTP/SSE transport for lower latency |
| LLM context | Single-turn with tool results | Multi-turn conversation history |
| Competitor scope | Enforced in SQL | Could also be enforced at MCP layer |
| Date handling | Tool default window when no dates passed | Explicit date required from frontend |
| Seed data | Synthetic, deterministic | Real anonymised retailer export |

**Out of scope for MVP:** authentication, background jobs, multi-turn chat memory, admin panels.

---

## Streaming chat (Phase 15)

The Analytics Assistant uses Server-Sent Events (`POST /api/chat/stream`) to give truthful, live progress before the final answer appears.

### Event flow

```
event: status   {"text": "Tolkar frågan…"}
event: status   {"text": "Hämtar relevanta analysdata…"}
   ← MCP subprocess opens; tool calls execute here →
event: status   {"text": "Sammanställer svaret…"}
event: delta    {"text": "Försäljningen under…"}   ← real OpenAI token stream
event: delta    {"text": " perioden uppgick…"}
…
event: complete {answer, chart, sources, tool_calls, limitations, supplier_id, generated_at}
```

### Design principles

- **Progress events are truthful stages, not simulated reasoning.** Each status label corresponds to a real step: guardrail check, MCP connection + tool execution, final LLM synthesis.
- **No numbers are emitted before MCP data is available.** Status and delta events carry only labels or answer text — never invented figures. The `complete` event is the only place where chart data and source metadata appear.
- **Answer text streams only after all tool results are collected.** OpenAI streaming is enabled only for the final synthesis call, after the tool-calling loop has fully completed.
- **Charts remain deterministic from MCP results.** The `chart` field in `complete` is built by `chart_builder.py` from validated MCP tool output, exactly as in the non-streaming endpoint. The LLM response text is never parsed for numbers.
- **Guardrail-blocked questions return a single `complete` event immediately** — no MCP subprocess is opened, no status/delta events are emitted.

### Smoke test

```bash
cd backend
python -m scripts.stream_smoke_test
```

The non-streaming endpoint (`POST /api/chat`) is preserved unchanged for backwards compatibility.
