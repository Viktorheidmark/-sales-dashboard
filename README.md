# Solvigo Sales Intelligence

En AI-driven försäljningsdashboard riktad till leverantörer. Leverantörer loggar in och ser hur deras produkter presterar över regioner, tidsperioder och kategorier – och kan ställa frågor på naturligt språk som besvaras av en AI-assistent som bygger sina svar på verkliga data.

Byggd som en MVP för ett utvecklarcase som visar MCP-baserad förankring av LLM-svar, separering mellan leverantörskonton och kontrollerad exponering av konkurrentdata.

---

## Problemet som löses

Detaljisterna äger all försäljningsdata. Leverantörer har historiskt saknat självbetjänad analys – de har varit beroende av långsamma och kostsamma rapporteringscykler. Den här dashboarden ger varje leverantör ett levande fönster mot sin egen prestanda utan att exponera konkurrenternas data på ordernivå eller andra leverantörers data.

AI-assistenten förankras genom Model Context Protocol (MCP): LLM:en anropar strukturerade analysverktyg i stället för att generera SQL eller resonera utifrån minnet. Varje kvantitativt påstående i ett chattsvar backas upp av ett verkligt verktygsresultat.

---

## Live demo

[Öppna Solvigo Sales Intelligence](https://sales-dashboard-xi-hazel.vercel.app/)

Applikationen använder enbart syntetisk demodata – ingen verklig försäljnings-, kund- eller marknadsdata förekommer.

Inloggningsuppgifter och en rekommenderad genomgång finns i [DEMO.md](DEMO.md).

---

## Arkitektur

```mermaid
graph LR
    A[React / Vite<br/>frontend] -->|REST JSON| B[FastAPI<br/>backend]
    B -->|OpenAI tool-calling loop| C[OpenAI API<br/>gpt-4o]
    C -->|tool call| B
    B -->|MCP stdio transport| D[FastMCP server<br/>mcp_server/]
    D -->|parameterised SQL<br/>SQLAlchemy| E[(Neon PostgreSQL)]
    B -->|direct import<br/>dashboard endpoints only| D
```

**Anropsflöde för AI-assistenten:**

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

## Varför MCP

Model Context Protocol låter backend exponera typade, leverantörsavgränsade analysverktyg som LLM:en anropar via namn – `get_supplier_kpis`, `get_top_products`, osv. Det innebär:

- LLM:en genererar aldrig SQL och rör aldrig databasen direkt.
- Backend injicerar `supplier_id` i varje verktygsanrop efter att LLM:en har bestämt vilket verktyg som ska anropas. Modellen kan varken välja eller åsidosätta det.
- De verktygsscheman som presenteras för LLM:en har `supplier_id` borttaget – modellen ser aldrig ens fältet.
- Konkurrentdata tvingas vara enbart aggregerad inuti varje verktygsfråga, oavsett vad LLM:en begär.

Dashboardens endpoints (utanför chatten) anropar samma `query_helpers`-funktioner direkt av prestandaskäl – endast chattflödet använder MCP:s stdio-transport.

---

## AI-nativ analysarkitektur

Analysförfrågningar löper genom en kanonisk orkestreringspipeline:

```
Question
→ structured plan
→ validation
→ tenant-safe data execution
→ result verification
→ grounded response and chart
```

- **Explicit periodjämförelse** (t.ex. *"jämför de senaste 30 dagarna med föregående 30"*) är migrerad till denna orkestrerade pipeline i `backend/app/analytics/`, styrd av funktionsflaggan `AI_ORCHESTRATED_ANALYTICS_ENABLED`.
- **Alla övriga avsikter** behåller det stabila äldre chattflödet (`backend/app/services/chat.py`) medan migreringen pågår – inget annat tvingas genom den nya pipelinen ännu.
- **Leverantörsavgränsningen härleds på serversidan** från den autentiserade sessionen i varje steg; planeraren och exekveraren litar aldrig på ett `supplier_id` som skickats från klienten.
- **Inga tysta gissningar:** när en jämförelseförfrågan saknar datum eller har tvetydiga datum returnerar valideringen ett strukturerat förtydligande (en periodväljare direkt i chatten) i stället för att hitta på ett datumintervall.

Pipelinen är medvetet inkrementell: varje steg går att testa fristående, och funktionsflaggan möjliggör omedelbar återgång till det äldre flödet.

---

## Sparade insikter och PDF-rapporter

Autentiserade leverantörsanvändare kan spara vilket förankrat chattsvar som helst (ett som backas upp av MCP-verktygsdata) och senare hämta eller exportera det som en polerad PDF-rapport.

**Beteende:**
- Insikter är leverantörsavgränsade – backend härleder `supplier_id` från sessionscookien; frontend skickar det aldrig.
- Läsningar, exporter eller raderingar mellan olika leverantörskonton returnerar alltid 404 (aldrig 403).
- Endast förankrade svar (de med `tool_calls.length > 0`) kan sparas – svar från skyddsregler, svar som inte stöds eller förtydligandesvar saknar knappen "Spara insikt".
- Diagramdatan lagras som JSONB och återges troget vid export; diagramvärden kommer alltid från MCP-resultat, aldrig från AI-genererad text.
- PDF är det enda exportformatet för användaren – inga publika delningslänkar eller massoperationer i denna MVP.

**PDF-rapportens format (A4):**
- Sidhuvudsband: bakgrund i slate-900, "◈ Solvigo Sales Intelligence" (varumärkesblå), leverantörsnamn (till höger), underrubriken "Analysrapport".
- Brödtext: fråga, analys (svarstext, rad för rad), diagram renderat som PNG via matplotlib (linje/stapel/cirkel), datakällor (källverktyg som läsbara svenska etiketter), begränsningar (i bärnstensgult).
- Sidfot: "Solvigo Sales Intelligence · Grundat i MCP-analyserad syntetisk demodata" + tidsstämpel för genereringen.
- Diagramrenderingen använder varumärkespaletten (`#4169e1`, `#a5b4fc`, `#c7d2fe`). Negativa stapelvärden (t.ex. minskande %) får `#ef4444`. Diagramblocket utelämnas tyst om inget diagram sparades.
- Inget `supplier_id`, ingen JWT, inga databas-URL:er och inga interna sökvägar förekommer i resultatet.

**Endpoints (alla kräver sessionscookie):**

| Metod | Sökväg | Syfte |
|---|---|---|
| `POST` | `/api/insights` | Spara en förankrad insikt |
| `GET` | `/api/insights` | Lista egna insikter (nyaste först, max 100) |
| `GET` | `/api/insights/{id}` | Fullständig detalj inklusive diagram |
| `DELETE` | `/api/insights/{id}` | Radera egen insikt |
| `GET` | `/api/insights/{id}/export.pdf` | Ladda ner polerad PDF-rapport i A4 |

PDF-generering: `backend/app/services/pdf_builder.py` – `reportlab` (Platypus, A4) + `matplotlib` (Agg-backend, PNG i minnet). Inga beroenden till webbläsare eller systemnivå.

Smoke-test: `python -m scripts.pdf_smoke_test` (8 fall, kräver att backend körs).

---

## Chattdiagram

Varje förankrat chattsvar kan inkludera en deterministisk diagramdata som renderas direkt i chattgränssnittet.

| Verktyg / avsikt | Diagramtyp | Anmärkningar |
|---|---|---|
| `get_sales_over_time` | linjediagram | intäkt över perioden (dag / vecka / månad) |
| `get_top_products` | horisontellt stapeldiagram | produktrankning efter intäkt |
| `get_sales_by_region` | horisontellt stapeldiagram | intäkt per region |
| `get_market_share` | ringdiagram (cirkeldiagram) | "Oss" mot aggregerade "Konkurrenter" |
| `get_declining_products` | stapeldiagram | %-förändring mot föregående period (negativa staplar i rött) |
| `get_supplier_kpis` | KPI-summor – eller jämförelsestaplar när en periodjämförelse begärs | intäkt, ordrar, enheter, AOV |
| Explicit periodjämförelse | jämförelsestapeldiagram | analyserad period mot baslinje, färgsatt per leverantör |

**Viktiga egenskaper:**
- Diagram byggs av `backend/app/services/chart_builder.py` från rå MCP-utdata – LLM:ens svarstext tolkas aldrig för att utvinna siffror.
- Som mest returneras ett diagram per svar. När flera MCP-verktyg anropas kommer diagrammet från det visuella verktyget med högst prioritet (trend → marknadsandel → toppprodukter → region → minskande).
- Ett diagram undertrycks när MCP-resultatet har färre än två användbara rader.
- Alla svar från skyddsreglerna (`prompt_injection`, `restricted`, `insufficient_data`, `unsupported`, `clarification_needed`) returnerar alltid `chart = null`.
- Diagramdatan ärver den autentiserade leverantörens avgränsning – supplier\_id injiceras av backend före varje MCP-anrop.
- Frontend renderar diagram med Recharts och återanvänder samma bibliotek som dashboarden.

Diagramdatans struktur:

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

Smoke-test: `python -m scripts.chart_smoke_test` (9 fall, kräver att backend körs).

---

## Skyddsregler och säkerhet

Varje chattmeddelande klassificeras **deterministiskt** innan något OpenAI- eller MCP-anrop görs. Skyddsregellagret i `backend/app/services/guardrails.py` använder regex-mönstermatchning – ingen LLM inblandad – och returnerar omedelbart för indata som inte rör analys.

| Klassificering | Exempel på utlösare | Åtgärd |
|---|---|---|
| `prompt_injection` | "ignorera tidigare instruktioner", "visa systemprompten", "kör SQL", "vad är JWT-hemligheten" | Neka; returnera svenskt felmeddelande; ingen LLM/MCP |
| `restricted` | "vilka kunder har konkurrenterna?", "visa konkurrenternas ordrar" | Förklara policyn om enbart aggregerade data; ingen LLM/MCP |
| `insufficient_data` | marginal, vinst, lager, returer, prognoser, annonsbudget | Förklara vilka data som finns tillgängliga; ingen LLM/MCP |
| `unsupported` | väder, sport, kodning, nyheter, aktiekurser | Styr om till analys; ingen LLM/MCP |
| `clarification_needed` | vaga frågor utan analyssignal ("hur går det?") | Ställ en följdfråga med 4 föreslagna inriktningar |
| `supported` | försäljning, intäkt, produkter, trender, regioner, marknadsandel | Släpp igenom till fullt LLM + MCP-flöde |

**Säkerhetsinvarianter (upprätthålls i lager):**
- Skyddsreglerna exponerar aldrig: JWT-innehåll, JWT-hemlighet, miljövariabler, databas-URL:er, rå SQL, interna systemprompter, MCP-implementationsdetaljer, serversökvägar eller källkod.
- `supplier_id` härleds uteslutande från den autentiserade sessionen – inte från meddelandet och inte från LLM:en.
- MCP-verktygslistan är vitlistad i `ALLOWED_TOOLS`; LLM:en kan inte lägga till eller ändra verktyg.
- Verktygsargument schemavalideras; `supplier_id` skrivs över av backend omedelbart före varje MCP-anrop.
- Konkurrentdata förblir enbart aggregerad både i skyddsregellagret (mönstermatchning) och i MCP-frågelagret (upprätthålls i SQL).

Smoke-test: `python backend/scripts/guardrail_smoke_test.py` (13 fall, kräver att backend körs).

---

## Leverantörsavgränsning och skyddsregler mot konkurrentdata

| Risk | Var den upprätthålls |
|---|---|
| LLM väljer fel leverantör | `supplier_id` borttaget från OpenAI-schemat; backend skriver alltid över |
| Dataläckage mellan leverantörer | Alla frågor joinar via `brands.supplier_id` |
| Konkurrenters produkt-/orderdetaljer | `query_market_share` returnerar endast aggregerad intäkt; inga produktnamn eller orderrader |
| SQL-injektion | Alla frågor använder SQLAlchemy `text()` med namngivna bind-parametrar |

---

## Förankring och källmetadata

Varje chattsvar innehåller:

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

Systemprompten injicerar dagens datum vid anropstillfället och instruerar modellen att citera det `date_range` som verktyget returnerar – inte att härleda kalenderperioder från sin träningsdata.

---

## Datamodell

```
Supplier → Brand → Product ← Category
                       ↓
Customer ← Region   OrderItem
    ↓                  ↑
  Order ──────────────┘

Supplier → SavedInsight
```

UUID-primärnycklar genomgående. `OrderItem` lagrar `quantity`, `unit_price` och förberäknad `revenue`. `SavedInsight` ligger till grund för funktionerna för sparade insikter och PDF-export (se "Sparade insikter och PDF-rapporter" ovan).

---

## Demoleverantörer

> **Synthetic demo data.** Företags- och produktnamn används endast i syntetisk demodata. Försäljningsdata, marknadsandelar och kunddata är inte verkliga.

Seed-skriptet skapar fyra leverantörskonton i två kategorier (Läsk samt Chips & snacks), där varje konto konkurrerar direkt med en rival. Varje demokonto är avgränsat till en enda leverantör.

| Leverantör | Inloggning | Kategori | Varumärken | Viktigt inseedat mönster |
|---|---|---|---|---|
| **Coca-Cola Europacific Partners Sverige** (primär demo) | `cocacola@demo.solvigo` | Läsk | Coca-Cola, Fanta, Sprite | Toppprodukt *Coca-Cola Zero Sugar 33 cl*; *Coca-Cola Zero Sugar Lemon* minskar de senaste 30 dagarna; ≈55 % andel av Läsk mot PepsiCo |
| **PepsiCo Northern Europe** | `pepsico@demo.solvigo` | Läsk | Pepsi, 7UP, Mountain Dew | Toppprodukt *Pepsi Max 33 cl*; *Pepsi Max Lime* ökar +50 % under de sista 90 dagarna; ≈45 % andel av Läsk |
| **Orkla Snacks Sverige (OLW)** | `olw@demo.solvigo` | Chips & snacks | OLW | ≈52 % andel av Chips & snacks mot Estrella |
| **Estrella AB** | `estrella@demo.solvigo` | Chips & snacks | Estrella | Toppprodukt *Estrella Grillchips 275 g*; *Estrella Cheddar 180 g* dippar de senaste 30 dagarna; *Estrella Linschips* växer +50 % |

Alla demokonton använder lösenordet `demo1234`. Konkurrenter visas endast som aggregerad intäkt i varandras marknadsandelsvy – aldrig på produkt- eller ordernivå. Inseedade regioner: Stockholm, Göteborg, Malmö.

---

## Lokal installation

### Förutsättningar

- Python 3.11+
- Node 18+
- En Neon PostgreSQL-databas (eller valfri PostgreSQL 14+)
- En OpenAI API-nyckel med åtkomst till `gpt-4o`

### 1 — Miljö

```bash
# Copy and fill in root .env (used by backend and MCP server)
cp .env.example .env
# Edit DATABASE_URL and OPENAI_API_KEY
```

Format för rot-`.env`:

```
DATABASE_URL=postgresql+psycopg://user:password@host:5432/dbname
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
```

> **Obs:** Använd schemat `postgresql+psycopg://` (synkron psycopg-drivrutin). `asyncpg` används inte.

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

### 4 — MCP-server (fristående, valfritt)

MCP-servern körs automatiskt som en subprocess till FastAPI-backenden. För att inspektera den fristående:

```bash
# From project root, with backend/.venv active
python -m mcp_server.server        # stdio transport
fastmcp dev mcp_server/server.py   # browser inspector (requires fastmcp CLI)
```

---

## Demoflöde

En föreslagen genomgång för en live-demo inför en utvärderare. Tar cirka 5 minuter.

1. **Logga in som Coca-Cola Europacific Partners Sverige** – öppna `http://localhost:5173`, klicka på demokontokortet "Coca-Cola Europacific Partners Sverige" (lösenordet är förifyllt) och klicka sedan på "Logga in". Dashboarden laddas med KPI:er, trend, toppprodukter, regioner, marknadsandel och minskande produkter för de senaste 90 dagarna.

2. **Granska dashboarden** – notera att panelerna "Omsättning", regionrankningar och "Marknadsandel" alla uppdateras från syntetisk demodata som hämtats via MCP. Ändra datumintervallet till "30 dagar" och se hur alla paneler uppdateras.

3. **Ställ en förankrad trendfråga** – scrolla till "Analytics Copilot" och skriv eller klicka:
   > *Hur ser vår försäljningstrend ut den senaste månaden?*
   Assistenten anropar `get_sales_over_time` via MCP (indikatorn "Hämtar data via MCP…" visas) och returnerar sedan ett svar på svenska med ett deterministiskt linjediagram. Diagrammet byggs från rå verktygsutdata – aldrig från AI-genererad text.

4. **Ställ en skyddad konkurrentfråga** – skriv:
   > *Vilka produkter säljer våra konkurrenter?*
   Skyddsregeln fångar upp detta deterministiskt (inget OpenAI-anrop görs) och returnerar en förklaring på svenska av policyn om enbart aggregerade konkurrentdata.

5. **Spara en diagraminsikt** – på det förankrade trendsvaret (som har källmärkningarna "via"), klicka på "Spara insikt". Knappen visar "✓ Sparad" när den sparats. Klicka på "☆ Insikter" i sidhuvudet för att öppna insiktspanelen och bekräfta att den sparade posten visas.

6. **Exportera en PDF-rapport** – öppna den sparade insikten och klicka på "↓ Exportera rapport som PDF". En polerad PDF i A4 laddas ner med varumärkt sidhuvud, svarstext, inbäddat diagram och datakällor. PDF:en genereras på serversidan från den sparade diagramdatan – inte från AI-text.

7. **Visa separeringen mellan leverantörskonton** – klicka på "Logga ut" och logga sedan in som "Estrella AB" (`estrella@demo.solvigo`, en leverantör i Chips & snacks). Bekräfta att dashboarden visar andra KPI:er i en annan kategori och att panelen "☆ Insikter" är tom (Coca-Colas insikter syns inte).

---

## Verifieringskommandon

Alla smoke-tester kräver att backend körs (`uvicorn app.main:app --reload`) om inget annat anges.

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

Förväntade resultat när demodata har seedats:

```
MCP smoke test:   6/6 passed
API smoke test:  16/16 passed
Chat smoke test:  7/7 passed
```

### Frontend-bygge

```bash
cd frontend
npm run build
```

---

## Interaktiv API-dokumentation

Med backend igång: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Föreslagna demofrågor (på svenska)

Ställ dessa i panelen Analytics Copilot som Coca-Cola Europacific Partners Sverige:

```
Vad är vår totala omsättning de senaste 90 dagarna?
Vilka är våra bästsäljande produkter?
Vilka produkter tappar mest i försäljning just nu?
Hur stor är vår marknadsandel i kategorin Läsk?
Hur ser vår försäljningstrend ut den senaste månaden?
Vilka är våra bästsäljande produkter i Stockholm?
Jämför vår omsättning de senaste 30 dagarna med föregående 30 dagar.
```

---

## API-endpoints

| Metod | Sökväg | Beskrivning |
|---|---|---|
| `GET` | `/health` | Tjänstens hälsa |
| `GET` | `/api/suppliers` | Lista leverantörer (id + namn) |
| `GET` | `/api/dashboard/overview` | KPI:er: intäkt, ordrar, enheter, AOV |
| `GET` | `/api/dashboard/sales-over-time` | Tidsserie (dag / vecka / månad) |
| `GET` | `/api/dashboard/top-products` | Toppprodukter efter intäkt, valfritt regionfilter |
| `GET` | `/api/dashboard/regions` | Intäkt per region |
| `GET` | `/api/dashboard/market-share` | Leverantörens andel inom en kategori |
| `GET` | `/api/dashboard/declining-products` | Produkter som minskar mot föregående period |
| `POST` | `/api/chat` | Förankrad AI-chatt |

---

## Avvägningar och kända begränsningar

| Område | Nuvarande lösning | Alternativ |
|---|---|---|
| Autentisering | E-post + lösenord med en signerad JWT-sessionscookie; leverantören härleds på serversidan från sessionen | Hanterad IdP (Auth0 / Supabase) med SSO per leverantör |
| MCP-transport | stdio-subprocess per chattförfrågan | HTTP/SSE-transport för lägre latens |
| LLM-kontext | En tur med verktygsresultat | Konversationshistorik över flera turer |
| Konkurrentavgränsning | Upprätthålls i SQL | Skulle även kunna upprätthållas i MCP-lagret |
| Datumhantering | Verktygets standardfönster när inga datum anges | Explicit datum krävs från frontend |
| Seed-data | Syntetisk, deterministisk | Verklig anonymiserad export från detaljist |

**Utanför ramen för MVP:n:** bakgrundsjobb, chatthistorik mellan sessioner, adminpaneler.

---

## Strömmade chattsvar (Fas 15)

Analysassistenten använder Server-Sent Events (`POST /api/chat/stream`) för att ge sanningsenlig, live-uppdaterad förloppsinformation innan det slutliga svaret visas.

### Händelseflöde

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

### Designprinciper

- **Förloppshändelser är sanningsenliga steg, inte simulerat resonemang.** Varje statusetikett motsvarar ett verkligt steg: skyddsregelkontroll, MCP-anslutning + verktygsexekvering, slutlig LLM-syntes.
- **Inga siffror skickas ut innan MCP-data finns tillgänglig.** Status- och delta-händelser bär endast etiketter eller svarstext – aldrig påhittade siffror. Händelsen `complete` är det enda ställe där diagramdata och källmetadata förekommer.
- **Svarstext strömmas först efter att alla verktygsresultat har samlats in.** OpenAI-strömning aktiveras endast för det slutliga syntesanropet, efter att verktygsanropsloopen har slutförts helt.
- **Diagram förblir deterministiska utifrån MCP-resultat.** Fältet `chart` i `complete` byggs av `chart_builder.py` från validerad MCP-verktygsutdata, precis som i den icke-strömmande endpointen. LLM:ens svarstext tolkas aldrig för att utvinna siffror.
- **Frågor som blockeras av skyddsreglerna returnerar omedelbart en enda `complete`-händelse** – ingen MCP-subprocess öppnas och inga status/delta-händelser skickas.

### Smoke-test

```bash
cd backend
python -m scripts.stream_smoke_test
```

Den icke-strömmande endpointen (`POST /api/chat`) bevaras oförändrad för bakåtkompatibilitet.

---

## Datafärskhet och kvalitet (Fas 16)

Varje dashboardsvar innehåller en tidsstämpel `generated_at` (tidpunkten för förfrågan) och ett fält `source` (t.ex. `MCP:get_supplier_kpis`). KPI-översiktssvaret innehåller även `latest_order_date` – det senaste `order_date`-värdet i databasen för den leverantören och perioden, härlett från `MAX(order_date)` över samma leverantörsavgränsade fråga som används för alla andra KPI-fält.

### Vad som visas

Under KPI-korten visas en kompakt metadatarad:

```
Dataperiod: 24 mars–22 juni 2026 · 771 ordrar · 2 913 sålda enheter
Senast transaktionsdatum: 22 juni 2026 · Beräknad: 22 juni 2026 20:10
```

- **Dataperiod** – det valda datumfönstret (från datumväljarens förval)
- **ordrar / sålda enheter** – verkliga antal för den leverantören och perioden
- **Senast transaktionsdatum** – `MAX(order_date)` från databasen; visar användarna hur färska data faktiskt är
- **Beräknad** – när backend-frågan kördes (tidpunkten för förfrågan)

Skillnaden är viktig: om data laddas kl. 20:10 men den senaste transaktionen var i går kan användarna se det direkt i stället för att anta att "nu = senaste data".

### Data-status-endpoint

`GET /api/dashboard/data-status` returnerar en dedikerad färskhetssammanfattning avgränsad till den autentiserade leverantören:

```json
{
  "supplier_id": "...",
  "period_start": "2026-03-24",
  "period_end": "2026-06-22",
  "latest_order_date": "2026-06-22",
  "total_orders": 771,
  "total_units": 2913,
  "generated_at": "2026-06-22T20:10:00Z",
  "limitations": []
}
```

`supplier_id` härleds alltid från den autentiserade sessionen – frontend kan inte ange eller åsidosätta det. Oautentiserade förfrågningar returnerar 401.

### MetaFooter

Alla dashboardkort visar "Beräknat från försäljningsdata · {source}" i kortets sidfot, vilket ersätter den tidigare etiketten "Live-data" som antydde realtidsanslutning.
