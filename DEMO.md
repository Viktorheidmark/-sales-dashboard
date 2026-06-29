# Solvigo Sales Intelligence — Demomanus

Ett demomanus för en cirka fem minuter lång live-demo eller skärminspelning.

---

## Live demo

[Öppna Solvigo Sales Intelligence](https://sales-dashboard-xi-hazel.vercel.app/)

Öppna alltid den stabila produktionslänken ovan – inte en deploy-specifik Vercel-URL.

Använd alltid länken ovan. Den följer senaste produktionsversionen.

---

## Innan du börjar

För live-demon behöver du inte starta något lokalt. Öppna bara länken ovan och logga in med ett demokonto.

För lokal utveckling och installation, se `README.md`.

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

## 5-minutersflöde

### Steg 1 — Logga in (15 s)

> "Appen är autentiserad. Jag loggar in som Coca-Cola Europacific Partners Sverige. Leverantörsavgränsningen är knuten till kontot – backend härleder leverantören från den autentiserade sessionen, inte från något som webbläsaren skickar."

Klicka på demoarbetsytan **Coca-Cola Europacific Partners Sverige** och sedan på **Logga in**.

### Steg 2 — Översikt av dashboarden (30 s)

> "Det här är en försäljningsdashboard riktad till leverantörer. Coca-Cola Europacific Partners Sverige ser aktuella KPI:er för den valda dataperioden – omsättning, antal ordrar och sålda enheter."

Peka på KPI-korten högst upp.

> "Data hämtas från PostgreSQL via parametriserade SQL-frågor när dashboarden laddas eller perioden ändras. Leverantörsavgränsningen upprätthålls på serversidan – en leverantör kan bara någonsin se sina egna data, och det aktiva kontots varumärkesfärg sätter temat för hela gränssnittet."

### Steg 3 — Diagram (30 s)

Scrolla till diagrammet för försäljningstrend.

> "Trenddiagrammet visar försäljningsutvecklingen för den valda perioden. Vi har seedat avsiktliga mönster för att göra demon meningsfull."

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

> "Assistenten gissar inte. Den hämtar svaret från den underliggande försäljningsdatan via ett analysverktyg och bygger sitt svar på det resultatet."

När svaret visas:

> "Svaret är avgränsat till Coca-Cola Europacific Partners Sverige – en leverantör kan aldrig se en annans data."

*(Tekniska detaljer om hur detta upprätthålls finns i avsnittet «Om du får tekniska frågor» nedan.)*

Ställ en följdfråga:

```
Vilka produkter tappar mest i försäljning just nu?
```

> "Assistenten hämtar data om produkter som tappat mest i försäljning. Varje kvantitativt påstående i svaret går att spåra tillbaka till ett verkligt verktygsresultat. Du kan också spara ett svar som en insikt och exportera det som en varumärkt PDF."

---

## Om du får tekniska frågor

Det här avsnittet är valfritt referensmaterial. Det behövs inte under själva demon, men ger underlag om en granskare ställer djupare tekniska frågor.

**Varför MCP-förankringen är pålitlig**

> "Traditionella LLM-analysverktyg ger modellen databasuppgifter och låter den generera SQL. Det skapar risker: modellen kan fråga vilken leverantörs data som helst, generera dyra eller felaktiga frågor och producera svar som inte är förankrade i verkligheten.
>
> Här anropar modellen namngivna verktyg med typade scheman. Backend injicerar leverantörsavgränsningen efter att modellen bestämt vilket verktyg som ska anropas – supplier_id härleds från den autentiserade sessionen och tas helt bort från det schema modellen ser. Konkurrentdata är enbart aggregerad på SQL-nivå, inte bara filtrerad i prompten."

**Detaljer bakom verktygsanropen**

- Modellen anropar typade verktyg (t.ex. `get_supplier_kpis`, `get_declining_products`) via MCP:s stdio-transport och har ingen direkt databasåtkomst.
- Varje verktyg kör en leverantörsavgränsad SQL-fråga och returnerar strukturerad JSON som svaret förankras i.
- `supplier_id` injiceras av backend från den autentiserade sessionen – LLM:en väljer det aldrig och ser det aldrig.
- Konkurrentavgränsningen upprätthålls i SQL-lagret, inte bara i prompten.

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

> "Varje del av dashboarden och varje chattsvar avgränsas automatiskt till den leverantör som är inloggad, och gränssnittet byter tema till det varumärkets färger."

Efter att du loggat in som en annan leverantör, fråga:

```
Hur ser vår regionala försäljning ut?
```
