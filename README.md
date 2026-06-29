# Solvigo Sales Intelligence

En AI-driven försäljningsdashboard för leverantörer. Varje leverantör loggar in och ser hur de egna produkterna presterar över regioner, tidsperioder och kategorier – och kan ställa frågor på naturligt språk som besvaras av en AI-assistent förankrad i verkliga data.

Projektet är byggt som en MVP för ett utvecklarcase. Det visar MCP-baserad förankring av LLM-svar, strikt separation mellan leverantörskonton och kontrollerad exponering av konkurrentdata.

---

## Live demo

[Öppna Solvigo Sales Intelligence](https://sales-dashboard-xi-hazel.vercel.app/)

All data är syntetisk demodata – ingen verklig försäljnings-, kund- eller marknadsdata förekommer.

Demolösenord för samtliga konton: `demo1234`.

Demokonton och en rekommenderad genomgång finns i [DEMO.md](DEMO.md).

---

## Problemet som löses

Detaljisterna äger all försäljningsdata, och leverantörer har historiskt saknat självbetjänad analys – de har varit beroende av långsamma och kostsamma rapporteringscykler. Dashboarden ger varje leverantör ett levande fönster mot sin egen prestanda, utan att exponera konkurrenternas data på order- eller produktnivå.

AI-assistenten förankras genom Model Context Protocol (MCP): LLM:en anropar strukturerade analysverktyg i stället för att generera SQL eller resonera utifrån minnet. Varje kvantitativt påstående i ett chattsvar backas upp av ett verkligt verktygsresultat.

---

## Vad som ingår

- **Leverantörsavgränsad dashboard** – KPI:er, trender och rankningar för det inloggade kontot.
- **AI-assistent förankrad i försäljningsdata** – svar på naturligt språk som bygger på verkliga verktygsresultat.
- **Trend, produkter, regioner och marknadsandel** – med diagram som genereras deterministiskt från data.
- **Explicit periodjämförelse** – jämför valfria perioder via en datumväljare direkt i chatten.
- **Separation mellan leverantörskonton och aggregerad konkurrentdata** – konkurrenter syns endast som aggregerad intäkt, aldrig på produkt- eller ordernivå.
- **Sparade insikter och PDF-export** – spara förankrade svar och exportera dem som varumärkta A4-rapporter.
- **Strömmande chattsvar** – live-uppdaterad förloppsinformation via Server-Sent Events.

---

## Teknikstack

React/Vite · FastAPI · Neon/PostgreSQL · OpenAI (`gpt-4o`) · MCP (FastMCP) · Recharts · Vercel (frontend) · Railway (backend)

---

## Arkitektur i korthet

```mermaid
graph LR
    A[React / Vite<br/>frontend] -->|REST JSON| B[FastAPI<br/>backend]
    B -->|OpenAI tool-calling loop| C[OpenAI API<br/>gpt-4o]
    C -->|tool call| B
    B -->|MCP stdio transport| D[FastMCP server<br/>mcp_server/]
    D -->|parameteriserad SQL| E[(Neon PostgreSQL)]
    B -->|direkt import<br/>endast dashboard| D
```

- **MCP-förankring:** LLM:en anropar typade, namngivna verktyg (`get_supplier_kpis`, `get_top_products`, …) och rör aldrig databasen direkt.
- **Leverantörsavgränsning på serversidan:** backend injicerar `supplier_id` i varje verktygsanrop efter att modellen valt verktyg – fältet tas bort från det schema modellen ser.
- **Deterministiska diagram:** diagramdata byggs från rå verktygsutdata, aldrig genom att tolka AI-genererad text.
- **Två vägar till samma datalager:** chatten använder MCP:s stdio-transport, medan dashboardens endpoints anropar samma frågefunktioner direkt av prestandaskäl.
- **AI-nativ orkestrering:** en kanonisk pipeline (plan → validering → tenant-säker exekvering → verifiering → förankrat svar) hanterar i dagsläget explicita periodjämförelser, medan övriga avsikter behåller det stabila äldre flödet.

---

## AI och säkerhet

- LLM:en skriver aldrig SQL och har ingen direkt databasåtkomst.
- `supplier_id` härleds uteslutande från den autentiserade sessionen – aldrig från meddelandet eller från modellen.
- Konkurrentdata är enbart aggregerad, vilket upprätthålls i SQL-lagret.
- Svar förankras i strukturerade verktygsresultat med källmetadata (verktyg, datumintervall, radantal).
- Ett deterministiskt skyddsregellager klassificerar varje meddelande innan något LLM- eller MCP-anrop görs och blockerar bl.a. promptinjektion och förfrågningar om konkurrenters detaljdata.

Djupare implementationsdetaljer (verktygsscheman, skyddsregelmönster, PDF- och diagrambyggare) finns i kodbasen.

---

## Lokal installation

### Förutsättningar

- Python 3.11+
- Node 18+
- En Neon PostgreSQL-databas (eller valfri PostgreSQL 14+)
- En OpenAI API-nyckel med åtkomst till `gpt-4o`

### 1 — Miljö

```bash
cp .env.example .env          # rot-.env, används av backend och MCP-server
cp frontend/.env.example frontend/.env
```

Fyll i `DATABASE_URL` och `OPENAI_API_KEY` i rot-`.env`. Använd schemat `postgresql+psycopg://` (synkron psycopg-drivrutin):

```
DATABASE_URL=postgresql+psycopg://user:password@host:5432/dbname
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
```

### 2 — Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

alembic upgrade head               # migreringar
python -m scripts.seed_demo_data   # ~2 000 ordrar, 4 leverantörer
uvicorn app.main:app --reload      # http://localhost:8000
```

### 3 — Frontend

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

Interaktiv API-dokumentation finns på [http://localhost:8000/docs](http://localhost:8000/docs) när backend körs.

---

## Test och kvalitet

```bash
# Backend-tester
cd backend && python -m unittest discover -s tests

# Frontend: typkontroll + bygge
cd frontend && npx tsc --noEmit
cd frontend && npm run build
```

Repot innehåller dedikerade smoke-tester för MCP-frågelagret, AI-chatten, diagram, skyddsregler, PDF-export och strömning (under `backend/scripts/` och `mcp_server/`). De flesta kräver att backend körs.

---

## Avvägningar och begränsningar

Detta är en MVP/arbetsprov, inte en färdig produkt.

| Område | Nuvarande lösning | Möjlig vidareutveckling |
|---|---|---|
| Autentisering | E-post + lösenord med signerad JWT-sessionscookie; leverantör härleds på serversidan | Hanterad IdP (Auth0/Supabase) med SSO |
| MCP-transport | stdio-subprocess per chattförfrågan | HTTP/SSE-transport för lägre latens |
| LLM-kontext | Varje fråga analyseras självständigt med färska verktygsresultat för tydlig datagrundning och förutsägbara svar | Konversationshistorik över flera turer, med fortsatt validering av tidigare valda filter och datumintervall |
| Datumhantering | Kalenderbaserat datumval för periodjämförelser, med standardperioder för fria frågor där inget datum anges | Fler naturliga datumtolkningar och konsekvent datumval i alla analystyper |
| Seed-data | Syntetisk och deterministisk | Verklig anonymiserad export från detaljist |
| Omfattning | Analys, sparade insikter och PDF | Bakgrundsjobb, chatthistorik och adminpaneler |

Datamodellen omfattar leverantörer, varumärken, produkter, ordrar, regioner och sparade insikter. PDF-export genereras på serversidan från den sparade förankrade insikten och dess diagramdata.

---

## Demo data

Seed-skriptet skapar fyra leverantörskonton i två kategorier (Läsk samt Chips & snacks), där varje konto konkurrerar direkt med en rival och är avgränsat till en enda leverantör:

- **Coca-Cola Europacific Partners Sverige** (`cocacola@demo.solvigo`) – primär demo, kategori Läsk
- **PepsiCo Northern Europe** (`pepsico@demo.solvigo`) – kategori Läsk
- **Orkla Snacks Sverige (OLW)** (`olw@demo.solvigo`) – kategori Chips & snacks
- **Estrella AB** (`estrella@demo.solvigo`) – kategori Chips & snacks

Alla demokonton använder lösenordet `demo1234`. All data är syntetisk. Fullständig genomgång finns i [DEMO.md](DEMO.md).
