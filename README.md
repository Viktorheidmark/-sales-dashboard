# Solvigo Sales Dashboard

A supplier-facing AI sales dashboard that allows suppliers (e.g. Nordic Coffee AB, Fresh Snacks Ltd, Clean Home Co) to explore how their own products perform across regions, categories, and time periods. The retailer owns all sales data; the dashboard surfaces it through a controlled, LLM-assisted interface that answers natural-language questions and renders charts grounded in real database results.

## Target architecture

```
React/Vite frontend
  → FastAPI backend
  → OpenAI API (LLM orchestration)
  → Custom Python MCP server
  → Neon Postgres (SQLAlchemy + Alembic)
```

## Core grounding principle

The LLM never accesses the database directly and never generates free-form SQL. All quantitative answers are grounded in results returned by controlled MCP tools. The FastAPI backend enforces supplier scope — the LLM cannot choose or override the active `supplier_id`. Competitor data is only exposed in aggregated form.

## Planned scope

- Revenue and sales KPIs per supplier
- Sales trends over time
- Top products
- Regional performance
- Market share within a category
- Saved insights
- Natural-language Q&A with chart/card responses

## Data model

```
Supplier → Brand → Product ← Category
                       ↓
Customer ← Region   OrderItem
    ↓                  ↑
  Order ──────────────┘

Supplier → SavedInsight
```

Key facts: UUID primary keys throughout. `OrderItem` stores `quantity`, `unit_price`, and `revenue`. `Product` carries a `sku` and current `unit_price`. `SavedInsight` stores the natural-language question, answer, optional `chart_payload` (JSONB), and `data_quality` score.

## Dashboard API

FastAPI serves the frontend with eight endpoints under `/api/`. It never queries the database directly — every endpoint calls the same parameterised query functions used by the MCP server (`mcp_server/query_helpers.py`), routed through `backend/app/services/analytics.py`.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health |
| GET | `/api/suppliers` | List demo suppliers (id + name) |
| GET | `/api/dashboard/overview` | KPIs: revenue, orders, units, AOV |
| GET | `/api/dashboard/sales-over-time` | Time series (day/week/month) |
| GET | `/api/dashboard/top-products` | Top products by revenue (optional region filter) |
| GET | `/api/dashboard/regions` | Revenue breakdown by region |
| GET | `/api/dashboard/market-share` | Supplier share within a category |
| GET | `/api/dashboard/declining-products` | Products declining vs prior period |

**Run the API:**
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

Interactive docs: http://localhost:8000/docs

**Smoke test** (requires server running):
```bash
python -m scripts.api_smoke_test
```

## MCP analytics server

The MCP server (`mcp_server/`) exposes six supplier-scoped analytics tools backed by Neon PostgreSQL. The LLM is never given a database connection and never generates SQL — it calls named tools that return structured JSON.

**Why typed, supplier-scoped tools?**
Free-form SQL access would let the LLM query any supplier's data, expose competitor details, and produce answers not grounded in controlled results. By enforcing supplier scope inside each tool (via the `brands → supplier_id` join) and returning aggregate-only competitor data, the backend guarantees what the LLM can and cannot see.

**Tools:** `get_supplier_kpis` · `get_sales_over_time` · `get_top_products` · `get_sales_by_region` · `get_market_share` · `get_declining_products`

Run the server: `python -m mcp_server.server` (stdio transport for MCP clients)
Interactive inspector: `fastmcp dev mcp_server/server.py`
Smoke test: `python -m mcp_server.smoke_test`

## Demo data

The database is seeded with realistic but synthetic retail data via `backend/scripts/seed_demo_data.py`. The script is safe to rerun (it clears and recreates demo tables).

The seed contains **intentional patterns** used to validate dashboard charts and natural-language Q&A:

- Nordic Coffee AB has the highest revenue in Stockholm and an upward trend over the last 90 days.
- Espresso Dark Roast 500g is Nordic Coffee's top product.
- Cold Brew Can shows a material revenue decline in the most recent 30 days.
- Fresh Snacks Ltd is relatively stronger in Malmö.
- Clean Home Co shows stable, lower growth across all regions.
- Competitor brands (Sparkling North, Nordic Sips) share categories with supplier brands to enable market-share queries.

To seed: `cd backend && python -m scripts.seed_demo_data`

## Out of scope (MVP)

Real authentication, deployment, PDF export, admin panels, RAG/vector databases, free-form SQL chat, background jobs.

## Frontend dashboard

React + Vite + TypeScript + Tailwind CSS + Recharts. Consumes the FastAPI dashboard API — no mock data.

**Sections:** KPI cards · Sales trend (line chart) · Top products (with region filter) · Regional sales (bar chart) · Market share (donut chart) · Declining products

**Start the frontend:**
```bash
cd frontend
cp .env.example .env       # edit VITE_API_BASE_URL if backend runs elsewhere
npm install
npm run dev                # http://localhost:5173
```

The supplier selector defaults to Nordic Coffee AB. Date range presets (30d / 90d / 180d / all time) control granularity automatically.

## Setup

### 1 — Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # fill in DATABASE_URL and OPENAI_API_KEY
alembic upgrade head
python -m scripts.seed_demo_data
uvicorn app.main:app --reload   # http://localhost:8000
```

### 2 — Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

### 3 — MCP server (standalone)

```bash
# From project root, with backend/.venv active
python -m mcp_server.server        # stdio transport
fastmcp dev mcp_server/server.py   # browser inspector
```
