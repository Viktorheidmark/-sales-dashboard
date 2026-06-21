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

## Out of scope (MVP)

Real authentication, deployment, PDF export, admin panels, RAG/vector databases, free-form SQL chat, background jobs.

## Setup

1. Copy `.env.example` to `.env` and fill in credentials.
2. Install backend dependencies: `cd backend && pip install -r requirements.txt`
3. Install frontend dependencies: `cd frontend && npm install`
4. Run backend: `uvicorn app.main:app --reload`
5. Run frontend: `npm run dev`
