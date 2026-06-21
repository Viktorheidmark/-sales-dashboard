# Pre-demo / Pre-submission Checklist

Work through this list top to bottom before running a demo or submitting.

## Environment

- [ ] Root `.env` exists and contains `DATABASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`
- [ ] `DATABASE_URL` uses `postgresql+psycopg://` scheme (not `asyncpg`)
- [ ] `frontend/.env` exists (copy from `frontend/.env.example` — defaults are fine for local dev)
- [ ] No secrets committed to git (`git status` shows `.env` as untracked/ignored)

## Backend setup

- [ ] Python virtual environment created: `cd backend && python -m venv .venv`
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] Database migrations applied: `alembic upgrade head`
- [ ] Demo data seeded: `python -m scripts.seed_demo_data` (safe to rerun)

## Smoke tests

Run all three from the `backend/` directory with the virtual environment active.
Backend must be running for the API and chat tests.

- [ ] **MCP smoke test** — `python -m mcp_server.smoke_test` → `6/6 passed`
- [ ] **API smoke test** — `python -m scripts.api_smoke_test` → `16/16 passed`
- [ ] **Chat smoke test** — `python -m scripts.chat_smoke_test` → `7/7 passed`

## Frontend

- [ ] Dependencies installed: `cd frontend && npm install`
- [ ] Build passes: `npm run build` (no TypeScript errors)
- [ ] Dev server starts: `npm run dev` → [http://localhost:5173](http://localhost:5173)

## Runtime checks

- [ ] Dashboard loads with Nordic Coffee AB selected
- [ ] KPI cards show non-zero revenue
- [ ] Sales trend chart renders a line
- [ ] Market share donut renders for Coffee category
- [ ] Declining products list shows Cold Brew Can
- [ ] Chat copilot returns a grounded Swedish answer for "Vad är vår totala omsättning?"
- [ ] Switching to Fresh Snacks Ltd updates all dashboard sections

## Git hygiene

- [ ] `.env` is not tracked: `git ls-files .env` returns empty
- [ ] `frontend/.env` is not tracked: `git ls-files frontend/.env` returns empty
- [ ] `frontend/dist/` is not tracked: `git ls-files frontend/dist` returns empty
- [ ] `backend/.venv/` is not tracked: `git ls-files backend/.venv` returns empty
