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

**Out of scope for MVP:** authentication, saved insights export, PDF reports, background jobs, multi-turn chat memory, real-time streaming responses, admin panels.
