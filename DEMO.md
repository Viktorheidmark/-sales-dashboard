# Solvigo Sales Intelligence — Demomanus

2-minuters genomgång för en live-demo eller skärminspelning.

---

## Innan du börjar

1. Backend igång: `cd backend && uvicorn app.main:app --reload`
2. Frontend igång: `cd frontend && npm run dev`
3. Öppna [http://localhost:5173](http://localhost:5173)
4. Du landar på **inloggningssidan**. Logga in med ett demokonto (se nedan) – varje konto är avgränsat till en leverantör.

### Demokonton

Alla demokonton delar lösenordet **`demo1234`**. På inloggningssidan visas de under **"Demoarbetsytor"** – klicka på ett för att automatiskt fylla i dess e-post och lösenord, och tryck sedan på **Logga in**.

| E-post | Leverantörskonto | Kategori |
|---|---|---|
| `cocacola@demo.solvigo` | Coca-Cola Europacific Partners Sverige | Läsk |
| `pepsico@demo.solvigo` | PepsiCo Northern Europe | Läsk |
| `olw@demo.solvigo` | Orkla Snacks Sverige | Chips & snacks |
| `estrella@demo.solvigo` | Estrella AB | Chips & snacks |

Den här genomgången använder **Coca-Cola Europacific Partners Sverige** (`cocacola@demo.solvigo`).

---

## 2-minutersflöde

### Steg 1 — Logga in (15 s)

> "Appen är autentiserad. Jag loggar in som Coca-Cola Europacific Partners Sverige. Leverantörsavgränsningen är knuten till kontot – backend härleder leverantören från den autentiserade sessionen, inte från något som webbläsaren skickar."

Klicka på demoarbetsytan **Coca-Cola Europacific Partners Sverige** och sedan på **Logga in**.

### Steg 2 — Översikt av dashboarden (30 s)

> "Det här är en försäljningsdashboard riktad till leverantörer. Coca-Cola Europacific Partners Sverige kan se sina egna KPI:er i realtid – intäkt, antal ordrar, sålda enheter och genomsnittligt ordervärde."

Peka på KPI-korten högst upp.

> "All data hämtas live från PostgreSQL via parametriserade SQL-frågor. Leverantörsavgränsningen upprätthålls på serversidan – en leverantör kan bara någonsin se sina egna data, och det aktiva kontots varumärkesfärg sätter temat för hela gränssnittet."

### Steg 3 — Diagram (30 s)

Scrolla till diagrammet för försäljningstrend.

> "Trendlinjen visar veckovis intäkt – vi har seedat avsiktliga mönster för att göra demon meningsfull."

Peka på Toppprodukter.

> "Coca-Cola Zero Sugar 33 cl är den intäktsmässigt största produkten."

Peka på Marknadsposition (kategorin Läsk).

> "I kategorin Läsk har Coca-Cola Europacific Partners Sverige omkring 55 % marknadsandel mot PepsiCos ~45 %. Konkurrenternas intäkt visas endast aggregerat – inga produktnamn, inga orderdetaljer."

### Steg 4 — Minskande produkter (15 s)

Scrolla till Minskande produkter.

> "Coca-Cola Zero Sugar Lemon flaggas som minskande – dess intäkt under de senaste 30 dagarna är väsentligt lägre än under föregående period. Detta är ett inseedat mönster för att visa varningsfunktionen."

### Steg 5 — Förankring i AI-assistenten (45 s)

Scrolla till panelen Analytics Copilot.

Skriv (eller klicka på exempelfrågan):

```
Vad är vår totala omsättning de senaste 90 dagarna?
```

Medan det laddar:

> "Modellen anropar `get_supplier_kpis` via MCP:s stdio-transport. Den har ingen databasåtkomst – den anropar ett typat verktyg som kör en leverantörsavgränsad SQL-fråga och returnerar strukturerad JSON. Svaret förankras i det resultatet."

När svaret visas:

> "supplier_id injicerades av backend från sessionen – LLM:en valde aldrig och såg det aldrig."

Ställ en följdfråga:

```
Vilka produkter tappar mest i försäljning just nu?
```

> "Modellen anropar `get_declining_products`. Varje kvantitativt påstående i det här svaret kan spåras tillbaka till ett verkligt verktygsresultat. Du kan också spara ett svar som en insikt och exportera det som en varumärkt PDF."

---

## Vad du kan säga om MCP-förankring

> "Traditionella LLM-analysverktyg ger modellen databasuppgifter och låter den generera SQL. Det skapar risker: modellen kan fråga vilken leverantörs data som helst, generera dyra eller felaktiga frågor och producera svar som inte är förankrade i verkligheten.
>
> Här anropar modellen namngivna verktyg med typade scheman. Backend injicerar leverantörsavgränsningen efter att modellen bestämt vilket verktyg som ska anropas – supplier_id härleds från den autentiserade sessionen och tas helt bort från det schema modellen ser. Konkurrentdata är enbart aggregerad på SQL-nivå, inte bara filtrerad i prompten."

---

## Vad du kan säga om nuvarande omfattning

| Fråga | Ärligt svar |
|---|---|
| Finns det autentisering? | Ja – inloggning med e-post + lösenord som backas upp av en signerad JWT-sessionscookie. Backend härleder `supplier_id` från sessionen vid varje förfrågan, aldrig från förfrågans innehåll. (Demokonton använder syntetiska uppgifter.) |
| Kan modellen se flera leverantörer? | Nej – varje verktygsanrop avgränsas av backend till den autentiserade leverantören, oavsett vad modellen skickar. |
| Kan leverantörer spara insikter? | Ja – svar kan sparas som insikter, listas på insiktssidan och exporteras som en PDF med leverantörens varumärke. |
| Kan den förklara sitt resonemang? | Verktygsmärkningarna och källmetadatan visar vilka verktyg som anropades och vilket datumintervall som täcktes. Hela tankekedjan visas inte. |
| Sparas chatthistoriken? | Följdfrågor behåller kontext inom en aktiv session (t.ex. "och föregående period?"), men konversationer sparas inte mellan inloggningar eller omladdningar. |

---

## Byt leverantör

Varje demokonto är avgränsat till en enda leverantör, så för att se ett annat konto **loggar du ut och loggar in som ett annat demokonto** (t.ex. `estrella@demo.solvigo` för Estrella AB i kategorin Chips & snacks).

> "Varje del av dashboarden och varje chattsvar omavgränsas automatiskt till den leverantör som är inloggad, och gränssnittet byter tema till det varumärkets färger."

Efter att du loggat in som en annan leverantör, fråga:

```
Hur ser vår regionala försäljning ut?
```
