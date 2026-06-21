# Solvigo Sales Intelligence — Demo Script

2-minute walkthrough for a live demo or screen recording.

---

## Before you start

1. Backend running: `cd backend && uvicorn app.main:app --reload`
2. Frontend running: `cd frontend && npm run dev`
3. Open [http://localhost:5173](http://localhost:5173)
4. Supplier pre-selected: **Nordic Coffee AB** (default)
5. Date preset: **Last 90 days** (default)

---

## 2-minute flow

### Step 1 — Dashboard overview (30 s)

> "This is a supplier-facing sales dashboard. Nordic Coffee AB can see their own KPIs in real time — revenue, order count, units sold, and average order value for the last 90 days."

Point to the KPI cards at the top.

> "All data is live from Neon PostgreSQL via parameterised SQL queries. The supplier scope is enforced server-side — a supplier can only ever see their own data."

### Step 2 — Charts (30 s)

Scroll to the Sales trend chart.

> "The trend line shows weekly revenue. You can see an upward slope over the last 90 days — we've seeded intentional patterns to make the demo meaningful."

Point to Top Products.

> "Espresso Dark Roast 500g is the top product by revenue."

Point to Market Share (set category to Coffee).

> "In the Coffee category, Nordic Coffee AB holds around 65% market share. Competitor revenue is shown aggregate-only — no product names, no order detail."

### Step 3 — Declining products (15 s)

Scroll to Declining Products.

> "Cold Brew Can and Cold Brew Bottle are flagged as declining — their revenue in the most recent 30 days is materially lower than the prior period. This is a seeded pattern to demonstrate the alert capability."

### Step 4 — AI Copilot grounding (45 s)

Scroll to the Analytics Copilot panel at the bottom.

Type (or click the example prompt):

```
Vad är vår totala omsättning de senaste 90 dagarna?
```

While it loads:

> "The model is calling `get_supplier_kpis` via MCP stdio transport. It doesn't have database access — it calls a typed tool that runs a supplier-scoped SQL query and returns structured JSON. The answer is grounded in that result."

When the answer appears, point to the tool badge:

> "You can see which tool was called. The supplier_id was injected by the backend — the LLM never chose or saw it."

Ask a follow-up:

```
Vilka produkter tappar mest i försäljning just nu?
```

> "The model calls `get_declining_products`. Every quantitative claim in this answer maps back to a real tool result."

---

## What to say about MCP grounding

> "Traditional LLM analytics tools give the model database credentials and let it generate SQL. That creates risks: the model can query any supplier's data, generate expensive or incorrect queries, and produce answers not grounded in reality.
>
> Here, the model calls named tools with typed schemas. The backend injects the supplier scope after the model decides which tool to call — supplier_id is stripped from the schema the model sees entirely. Competitor data is aggregate-only at the SQL level, not just filtered in the prompt."

---

## What to say about current limitations

| Question | Honest answer |
|---|---|
| Can suppliers save insights? | Not in the MVP — scaffolded in the data model but not wired to the UI. |
| Is there authentication? | No — demo only. In production each supplier would authenticate and the backend would derive supplier_id from the session, not the request body. |
| Can the model see multiple suppliers? | No — every tool call is scoped to the requesting supplier by the backend, regardless of what the model sends. |
| Can it explain its reasoning? | The tool badges and source metadata show which tools were called and which date range was covered. Full chain-of-thought is not surfaced. |
| Does chat history persist? | No — each chat session is stateless. |

---

## Switch supplier

Select **Fresh Snacks Ltd** from the supplier dropdown.

> "Fresh Snacks is relatively stronger in Malmö — you can see it in the Regions chart. Every dashboard section and every chat answer scopes automatically to this supplier."

Ask:

```
Hur ser vår regionala försäljning ut?
```
