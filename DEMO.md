# Solvigo Sales Intelligence — Demo Script

2-minute walkthrough for a live demo or screen recording.

---

## Before you start

1. Backend running: `cd backend && uvicorn app.main:app --reload`
2. Frontend running: `cd frontend && npm run dev`
3. Open [http://localhost:5173](http://localhost:5173)
4. You land on the **login page**. Sign in with a demo account (see below) — each account is scoped to one supplier tenant.

### Demo accounts

All demo accounts share the password **`demo1234`**. On the login page they appear under **"Demoarbetsytor"** — click one to auto-fill its email and the password, then press **Logga in**.

| Email | Supplier tenant | Category |
|---|---|---|
| `cocacola@demo.solvigo` | Coca-Cola Europacific Partners Sverige | Läsk |
| `pepsico@demo.solvigo` | PepsiCo Northern Europe | Läsk |
| `olw@demo.solvigo` | Orkla Snacks Sverige | Chips & snacks |
| `estrella@demo.solvigo` | Estrella AB | Chips & snacks |

This walkthrough uses **Coca-Cola Europacific Partners Sverige** (`cocacola@demo.solvigo`).

---

## 2-minute flow

### Step 1 — Log in (15 s)

> "The app is authenticated. I'll sign in as Coca-Cola Europacific Partners Sverige. The supplier scope is tied to the account — the backend derives the supplier from the authenticated session, not from anything the browser sends."

Click the **Coca-Cola Europacific Partners Sverige** demo workspace, then **Logga in**.

### Step 2 — Dashboard overview (30 s)

> "This is a supplier-facing sales dashboard. Coca-Cola Europacific Partners Sverige can see their own KPIs in real time — revenue, order count, units sold, and average order value."

Point to the KPI cards at the top.

> "All data is live from PostgreSQL via parameterised SQL queries. The supplier scope is enforced server-side — a supplier can only ever see their own data, and the active tenant's brand colour themes the whole UI."

### Step 3 — Charts (30 s)

Scroll to the Sales trend chart.

> "The trend line shows weekly revenue — we've seeded intentional patterns to make the demo meaningful."

Point to Top Products.

> "Coca-Cola Zero Sugar 33 cl is the top product by revenue."

Point to Market Position (Läsk category).

> "In the Läsk (soft drinks) category, Coca-Cola Europacific Partners Sverige holds around 55% market share versus PepsiCo's ~45%. Competitor revenue is shown aggregate-only — no product names, no order detail."

### Step 4 — Declining products (15 s)

Scroll to Declining Products.

> "Coca-Cola Zero Sugar Lemon is flagged as declining — its revenue in the most recent 30 days is materially lower than the prior period. This is a seeded pattern to demonstrate the alert capability."

### Step 5 — AI Copilot grounding (45 s)

Scroll to the Analytics Copilot panel.

Type (or click the example prompt):

```
Vad är vår totala omsättning de senaste 90 dagarna?
```

While it loads:

> "The model is calling `get_supplier_kpis` via MCP stdio transport. It doesn't have database access — it calls a typed tool that runs a supplier-scoped SQL query and returns structured JSON. The answer is grounded in that result."

When the answer appears:

> "The supplier_id was injected by the backend from the session — the LLM never chose or saw it."

Ask a follow-up:

```
Vilka produkter tappar mest i försäljning just nu?
```

> "The model calls `get_declining_products`. Every quantitative claim in this answer maps back to a real tool result. You can also save an answer as an insight and export it as a branded PDF."

---

## What to say about MCP grounding

> "Traditional LLM analytics tools give the model database credentials and let it generate SQL. That creates risks: the model can query any supplier's data, generate expensive or incorrect queries, and produce answers not grounded in reality.
>
> Here, the model calls named tools with typed schemas. The backend injects the supplier scope after the model decides which tool to call — supplier_id is derived from the authenticated session and stripped from the schema the model sees entirely. Competitor data is aggregate-only at the SQL level, not just filtered in the prompt."

---

## What to say about current scope

| Question | Honest answer |
|---|---|
| Is there authentication? | Yes — email + password login backed by a signed JWT session cookie. The backend derives `supplier_id` from the session on every request, never from the request body. (Demo accounts use synthetic credentials.) |
| Can the model see multiple suppliers? | No — every tool call is scoped to the authenticated supplier by the backend, regardless of what the model sends. |
| Can suppliers save insights? | Yes — answers can be saved as insights, listed on the Insights page, and exported as a tenant-branded PDF. |
| Can it explain its reasoning? | The tool badges and source metadata show which tools were called and which date range was covered. Full chain-of-thought is not surfaced. |
| Does chat history persist? | Follow-up questions keep context within an active session (e.g. "and the previous period?"), but conversations are not persisted across logins or reloads. |

---

## Switch supplier

Each demo account is scoped to a single supplier, so to view another tenant you **log out and log in as a different demo account** (e.g. `estrella@demo.solvigo` for Estrella AB in the Chips & snacks category).

> "Every dashboard section and every chat answer re-scopes automatically to whichever supplier is signed in, and the UI re-themes to that brand's colours."

After signing in as another supplier, ask:

```
Hur ser vår regionala försäljning ut?
```
