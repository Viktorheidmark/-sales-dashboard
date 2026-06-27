"""
Executive response-writing guidance for chat synthesis.

Kept separate from orchestration so prompts stay maintainable and testable.
"""

from __future__ import annotations

import re

from app.services.intent_router import is_diagram_followup_request, is_sales_status_question
from app.services.comparison_labels import question_requests_comparison

_FORBIDDEN_PHRASES = (
    "utvecklats enligt följande",
    "detta innebär att",
    "representeras av en aktör",
    "en konkurrent representerad",
    "kundpreferenser",
    "överväg strategier",
    "överväg att fokusera på marknadsföring",
    "överväg att analysera",
    "analysera längre perioder",
    "analysera specifika produktprestationer",
    "vidta strategier",
    "dominerar marknaden",
    "tillväxtmöjligheter",
    "framgångsfaktorer",
    "tillväxtområden",
    "identifiera potentiella",
    "för att fortsätta denna",
    "kan det vara fördelaktigt",
    "det kan vara fördelaktigt",
    "rekommenderas att",
    "bör överväga att",
    "föregående period",
    "tidigare period",
    "baserat på data",
    "analysen visar",
)

_UNSUPPORTED_ADVICE_RE = re.compile(
    r"(stärka marknadsföringen|sänk priset|lagerproblem|"
    r"öka marknadsföringsbudgeten|satsa mer på marknadsföring|"
    r"kundpreferenser|överväg strategier|prissättning|"
    r"marknadsföringsinsatser|lageroptimering|"
    r"överväg att fokusera på marknadsföring|fokusera på marknadsföring|"
    r"fokusera på marknadsföring|"
    r"överväg att analysera|"
    r"analysera specifika produktprestationer|vidta strategier|"
    r"kampanj|distribution|lageråtgärd|prisändring|"
    r"tillväxtmöjligheter|framgångsfaktorer|tillväxtområden|"
    r"identifiera potentiella|"
    r"för att fortsätta|kan det vara fördelaktigt|det kan vara fördelaktigt|"
    r"rekommenderas att|bör överväga att|"
    r"analysera vidare|fortsätta denna positiva)",
    re.IGNORECASE,
)

_VAGUE_COMPARISON_RE = re.compile(
    r"(jämfört med|mot)\s+(den\s+)?(föregående|tidigare)\s+period\b",
    re.IGNORECASE,
)
_VAGUE_COMPARISON_BARE_RE = re.compile(
    r"jämfört med\s+(tidigare|föregående)\b(?!\s+\d)",
    re.IGNORECASE,
)
_GENERIC_RECOMMENDATION_TAIL_RE = re.compile(
    r"\s*(För att (fortsätta|förbättra|upprätthålla)|"
    r"Det kan vara (fördelaktigt|bra)|"
    r"kan det vara fördelaktigt att|"
    r"rekommenderas att|bör överväga att|"
    r"kan vara värt att analysera).*$",
    re.IGNORECASE | re.DOTALL,
)

_SUPPLIER_PRODUCT_CONCAT_RE = re.compile(
    r"arla sverige\s+(iced|mellanmjölk|standardmjölk|keso)",
    re.IGNORECASE,
)

_MARKET_SHARE_RE = re.compile(r"marknadsandel|konkurrent|märke|andel", re.I)
_TOP_PRODUCTS_RE = re.compile(r"produkt|topp|säljer bäst|bästsälj", re.I)
_DECLINING_RE = re.compile(r"nedgång|minskat|fallit|tappar|sjunk", re.I)
_TREND_RE = re.compile(r"trend|utvecklat|försäljning.*90|senaste 90|senaste \d+ dag", re.I)
_WEEKLY_SALES_RE = re.compile(r"senaste\s+veck|hur såg försäljningen ut", re.I)
_FOCUS_RE = re.compile(r"fokusera|prioritera|nästa period|vad borde|vad bör", re.I)
_STRONG_DECLINE_RE = re.compile(r"nedåtgående\s+trend", re.I)
_VISADE_NEDGANG_RE = re.compile(
    r"\bvisade\s+en\s+nedåtgående\s+trend\s+(under\s+perioden)",
    re.IGNORECASE,
)
_HAR_NEDGANG_RE = re.compile(r"\bhar\s+en\s+nedåtgående\s+trend\b", re.IGNORECASE)
_DOUBLE_PERIOD_RE = re.compile(
    r"\bvarierade\s+under\s+perioden\s+under\s+perioden\b",
    re.IGNORECASE,
)

_UNREQUESTED_COMPARE_SENTENCE_RE = re.compile(
    r"(jämfört\s+med\s+(föregående|tidigare)|mot\s+(föregående|tidigare)\s+period|"
    r"föregående\s+\d+\s+dag|ökat\s+markant\s+från|minskat\s+markant)",
    re.IGNORECASE,
)


def _soft_trend_phrase(series: list[dict]) -> str:
    revs = [float(p.get("revenue") or 0) for p in series if p.get("revenue") is not None]
    if len(revs) >= 2 and max(revs) > revs[-1]:
        return "De senaste avslutade veckorna låg lägre än periodens topp"
    return "Försäljningen varierade under perioden"


def is_sustained_revenue_decline(series: list[dict]) -> bool:
    revs = [float(p.get("revenue") or 0) for p in series if p.get("revenue") is not None]
    if len(revs) < 4:
        if len(revs) >= 3 and revs[-1] < revs[-2] < revs[-3]:
            return False
        return False
    peak = max(revs)
    peak_idx = revs.index(peak)
    tail = revs[peak_idx + 1:]
    if len(tail) < 3:
        return False
    return all(r < peak for r in tail) and all(
        tail[i] <= tail[i - 1] for i in range(1, len(tail))
    )


def sanitize_trend_wording(
    answer: str,
    raw_tool_results: list[tuple[str, dict]] | None = None,
) -> str:
    if not claims_unsupported_strong_decline(answer, raw_tool_results):
        return answer

    out = _VISADE_NEDGANG_RE.sub(r"varierade \1", answer)
    out = _HAR_NEDGANG_RE.sub("varierade under perioden", out)
    out = _STRONG_DECLINE_RE.sub("varierade under perioden", out)
    return _DOUBLE_PERIOD_RE.sub("varierade under perioden", out)


def claims_unsupported_strong_decline(
    answer: str,
    raw_tool_results: list[tuple[str, dict]] | None,
) -> bool:
    if not _STRONG_DECLINE_RE.search(answer or ""):
        return False
    for name, result in raw_tool_results or []:
        if name == "get_sales_over_time":
            return not is_sustained_revenue_decline(result.get("series") or [])
    return True


def executive_writing_rules(supplier_name: str) -> str:
    name = supplier_name.strip() or "leverantören"
    forbidden = "; ".join(f'"{p}"' for p in _FORBIDDEN_PHRASES)
    return f"""
SKRIVSTANDARD (obligatorisk):
- Skriv som en skarp svensk kommersiell analytiker — inte som en rå dataexport.
- Struktur: 2–3 korta stycken. Första meningen = direkt svar på frågan.
- Förbjudna inledningar: "Under perioden", "Baserat på data", "Analysen visar", "För {name}".
- Använd "ni", "er", "ert" eller utelämna leverantörsnamn naturligt. Upprepa INTE hela leverantörsnamnet om det inte behövs.
- PRODUKTNAMN: kopiera exakt product_name från verktygsresultat. Sätt ALDRIG leverantörsnamnet framför produktnamnet
  om det inte redan ingår i product_name (t.ex. skriv "Coca-Cola Zero Sugar 33 cl", INTE "{name} Zero Sugar").
- Siffror i läsbar svensk form: 5,0 mkr · 800 tkr · 357 047 enheter · 13 215 ordrar · 59,1 %.
- Omsättning: använd VALUTAREFERENS och VALUTAFORMAT — under 1 000 kr, 1 000–999 999 tkr, från 1 000 000 mkr.
- Period: väv in period_label_answer naturligt (t.ex. "under hela perioden", "hittills i år") — ALDRIG rå ISO-intervall
  som inledning (t.ex. inte "2024-06-23 till 2026-06-22" i första meningen).
- Max cirka 90 ord om inte användaren uttryckligen ber om detaljer.
- Hitta aldrig på orsaker, rekommendationer eller siffror som saknas i verktygsdata.
- Nämn aldrig MCP, verktygsanrop, JSON, planner, databas eller implementation.
- Avsluta INTE med generiska råd ("för att fortsätta...", "kan det vara fördelaktigt att analysera...").
- Vid periodjämförelse: använd exakt jämförelsebas från JÄMFÖRELSE- OCH PERIODKRAV när den finns.
- Berätta ALDRIG för användaren att jämförelsedata saknas, att en föregående period inte existerar,
  eller att procentuell förändring inte kan beräknas. Om ingen jämförelse är möjlig: utelämna
  jämförelsen helt och beskriv enbart vad tillgänglig data visar — trend, total och nyckelobservationer.
- Förbjudna fraser och liknande: {forbidden}.

EXEMPEL PÅ BRA TON:
- "Ni har 59,1 % av marknaden inom Läsk under hela perioden."
- "Coca-Cola Zero Sugar är tydligt er starkaste produkt, med 5,0 mkr i omsättning och 357 047 sålda enheter."
- "Försäljningen är stabil hittills i år. Omsättningen är 4,5 mkr, vilket är i nivå med samma period förra året."
- "Coca-Cola Zero Sugar Lemon har tappat mest: omsättningen är ned 56,5 % jämfört med föregående 30 dagarna."
"""


def synthesis_blueprint(question: str, tools_used: list[str], supplier_name: str = "") -> str:
    q = question.strip()
    tools = set(tools_used)
    name = supplier_name.strip() or "leverantören"

    if "get_market_share" in tools or _MARKET_SHARE_RE.search(q):
        return """
FRÅGETYP: Marknadsandel
- Styck 1: Börja direkt med er andel i procent och kategori (t.ex. "Ni har 59,1 % av marknaden inom Läsk under hela perioden.").
- Styck 2: Er omsättning, kategoritotal och övriga aktörers andel i procent ("Övriga aktörer står tillsammans för X %").
- Använd period_label_answer naturligt — aldrig rå ISO-datum i inledningen.
- Skriv "Övriga aktörer" — nämn inte antal konkurrenter, produkter eller enskilda konkurrentnamn.
- Max 2–3 korta stycken. Ingen rekommendation eller strategiråd.
"""

    if (
        "get_sales_over_time" in tools
        and "get_supplier_kpis" in tools
        and (is_sales_status_question(q) or not question_requests_comparison(q))
    ):
        return """
FRÅGETYP: Försäljningsöversikt (utan jämförelse)
- Styck 1: Direkt slutsats om omsättning för perioden (period_label_answer), med belopp.
- Styck 2: Ordrar och enheter om relevant.
- Nämn INTE procentuell förändring, jämförelse mot föregående period eller tidigare omsättning.
- Beskriv gärna övergripande trend om series-data finns — utan att jämföra mot en annan period.
- Max 2–3 korta stycken. Ingen rekommendation.
"""

    if "get_supplier_kpis" in tools and question_requests_comparison(q):
        return """
FRÅGETYP: Översikt (KPI) med jämförelse
- Styck 1: Direkt slutsats om omsättning för perioden (period_label_answer), med belopp.
- Styck 2: Ordrar och enheter om relevant.
- Styck 3: Procentuell förändring mot jämförelsebas — använd OBLIGATORISK JÄMFÖRELSETEXT ordagrant när den finns.
  Om ingen tillförlitlig jämförelsebas finns: säg det tydligt utan att hitta på siffror.
- Använd "ni/er" — inte fullt leverantörsnamn i inledningen.
- Max 3 korta stycken. Ingen rekommendation.
"""

    if "get_supplier_kpis" in tools:
        return """
FRÅGETYP: Översikt (KPI)
- Styck 1: Direkt slutsats om omsättning för perioden (period_label_answer), med belopp.
- Styck 2: Ordrar och enheter om relevant.
- Nämn INTE jämförelse mot föregående period om användaren inte bad om det.
- Max 2–3 korta stycken. Ingen rekommendation.
"""

    if "get_top_products" in tools or (_TOP_PRODUCTS_RE.search(q) and "nedgång" not in q.lower()):
        return """
FRÅGETYP: Topprodukter
- Styck 1: Namnge starkaste produkten direkt med exakt product_name, omsättning och sålda enheter.
  Väv in period_label_answer naturligt (t.ex. "under hela perioden") — inte som inledning med ISO-datum.
- Styck 2: Nästa produkter enligt ranking och requested_limit — med omsättning. Nämn gap till tvåan om meningsfullt.
- Styck 3: En kort, datastödd kommersiell tolkning (t.ex. sortimentsmotor, tydlig ledare) — inga påhittade orsaker.
- Nämn ENDAST produkter i verktygsresultat. Lista inte fler än requested_limit.
- Nämn region endast om den finns i verktygsresultat och är relevant.
"""

    if "get_revenue_drivers" in tools:
        return """
FRÅGETYP: Omsättningsutveckling (30 dagar)
- Börja med total omsättningsförändring mellan senaste och föregående 30-dagarsperiod (absolut och %).
- Nämn ordrar och enheter om de förstärker bilden.
- Lyft största positiva produktbidrag och största negativa produktbidrag med exakta product_name.
- Nämn region med starkast respektive svagast förändring om datan finns.
- Max 3 korta stycken. Ingen rekommendation.
"""

    if "get_declining_products" in tools or _DECLINING_RE.search(q):
        return """
FRÅGETYP: Produkter i nedgång
- Om products-listan är tom: säg att inga produkter har negativ omsättningsförändring i vald jämförelse.
  Nämn INGEN produkt som tappat.
- Om products innehåller rader: börja med produkten med störst absolut omsättningstapp i kronor (revenue_change)
  — exakt product_name, absolut SEK-förändring, sedan procent.
- products-listan är sorterad efter störst absolut SEK-tapp — använd alltid första raden som huvudprodukt.
- Använd comparison_period_label / jämförelsebas från verktygsdata för båda jämförelsefönstren.
- Nämn ENDAST produkter som finns i products-listan.
- Inga antaganden om pris, lager eller marknadsföring.
"""

    if "get_sales_over_time" in tools and is_diagram_followup_request(q):
        return f"""
FRÅGETYP: Diagramuppföljning (försäljning)
- Om chart_context.widened är true: förklara att diagrammet visar flera avslutade veckor för sammanhang
  (t.ex. "de senaste 8 avslutade veckorna") — INTE som om det vore svaret på en enveckasfråga.
- Behåll fokus på den vecka som användaren frågade om tidigare via original_date_range; hänvisa kort till den.
- Använd date_range och analysed_range_label för diagrammets faktiska period.
- Max 2–3 meningar om mönstret i diagrammet.
- Använd INTE "nedåtgående trend" om variationen är blandad.
"""

    if "get_sales_over_time" in tools and _WEEKLY_SALES_RE.search(q):
        return f"""
FRÅGETYP: Senaste avslutade veckan
- Börja direkt med veckans resultat: omsättning, ordrar och enheter.
- Ange period naturligt via completed_week_label eller period_label_answer — inte rå ISO i inledningen.
- En kort jämförelse: om weekly_comparison_available är false, använd comparison_note.
  Om två eller fler fullständiga veckor finns: kort jämförelse mot föregående avslutade vecka.
- Max cirka 60 ord. Ingen rekommendation.
- Nämn ALDRIG pågående vecka, serien, ofullständig period eller intern databehandling.
"""

    if "get_sales_over_time" in tools or _TREND_RE.search(q):
        return f"""
FRÅGETYP: Försäljningstrend
- Styck 1: Direkt trendslutsats — uppåt, nedåt, stabilt eller blandat — med kärnsiffra om den tillför värde.
- Styck 2: Period naturligt via period_label_answer eller analysed_range_label. Omsättning, ordrar eller enheter om relevant.
- Styck 3: Högst en observation om topp, dip eller snitt — endast om den tillför värde.
- Beskriv övergripande riktning — ingen månad-för-månad-lista om användaren inte bett om det.
- TRENDSPRÅK: "nedåtgående trend" endast vid tydlig ihållande nedgång. Vid blandad utveckling: "stabil", "varierad" eller "blandad".
- Om analysis_note finns: nämn INTE ofullständig period i brödtexten.
- Ingen avslutande rekommendation. Vid jämförelse: exakt jämförelsebas — aldrig bara "föregående period".
"""

    if _FOCUS_RE.search(q):
        return """
FRÅGETYP: Fokus nästa period
- Kort prioritering: vilken produkt/kategori/region som sticker ut enligt data.
- Högst en datastödd observation — inga generiska åtgärdslistor.
- Ingen marknadsföring, prissättning, lager eller kundpreferenser utan datastöd.
"""

    return """
FRÅGETYP: Allmän analys
- Direkt svar först, sedan kompakta fakta. Om data saknas: säg det tydligt och föreslå vad som går att analysera istället.
- Hitta aldrig på siffror eller orsaker.
"""


def synthesis_suffix(supplier_name: str, question: str, tools_used: list[str]) -> str:
    return (
        "\n\n[Instruktion: Verktygsdata är hämtad. Skriv slutgiltigt svar direkt på svenska. "
        "Följ SKRIVSTANDARD och FRÅGETYP nedan.]"
        f"{executive_writing_rules(supplier_name)}"
        f"{synthesis_blueprint(question, tools_used, supplier_name)}"
    )


def has_vague_comparison(answer: str) -> bool:
    text = answer or ""
    return bool(_VAGUE_COMPARISON_RE.search(text) or _VAGUE_COMPARISON_BARE_RE.search(text))


def has_generic_recommendation(answer: str) -> bool:
    return bool(_GENERIC_RECOMMENDATION_TAIL_RE.search(answer or ""))


def sanitize_vague_comparisons(
    answer: str,
    raw_tool_results: list[tuple[str, dict]] | None = None,
    question: str = "",
) -> str:
    if not answer or not raw_tool_results:
        return answer
    from app.services.comparison_labels import comparison_metadata

    meta = comparison_metadata(raw_tool_results, question=question)
    explicit = meta.get("kpi_comparison_label") or ""
    if not explicit:
        for name, result in raw_tool_results:
            if name == "get_revenue_drivers" and isinstance(result, dict):
                from app.services.comparison_labels import revenue_drivers_comparison_label
                explicit = revenue_drivers_comparison_label(result)
                break
    if not explicit:
        return answer

    out = answer
    for pattern in (_VAGUE_COMPARISON_RE, _VAGUE_COMPARISON_BARE_RE):
        out = pattern.sub(explicit, out)
    out = re.sub(
        r"mot\s+(den\s+)?(föregående|tidigare)\s+period\b",
        explicit,
        out,
        flags=re.IGNORECASE,
    )
    return out


def strip_unrequested_comparison(answer: str, question: str) -> str:
    """Remove comparison sentences when the user did not ask to compare periods."""
    if not answer or question_requests_comparison(question):
        return answer
    parts = re.split(r"(?<=[.!?])\s+", answer.strip())
    kept = [p for p in parts if p and not _UNREQUESTED_COMPARE_SENTENCE_RE.search(p)]
    if not kept:
        return answer
    return " ".join(kept)


def sanitize_generic_recommendations(answer: str) -> str:
    if not answer:
        return answer
    return _GENERIC_RECOMMENDATION_TAIL_RE.sub("", answer).strip()


def has_unsupported_recommendation(answer: str) -> bool:
    return bool(_UNSUPPORTED_ADVICE_RE.search(answer or ""))


def misnames_product(answer: str, supplier_name: str = "") -> bool:
    if _SUPPLIER_PRODUCT_CONCAT_RE.search(answer or ""):
        return True
    if not supplier_name:
        return False
    sn = supplier_name.strip().lower()
    if not sn:
        return False
    for token in ("iced coffee", "mellanmjölk", "standardmjölk", "keso cottage"):
        if f"{sn} {token}" in (answer or "").lower():
            return True
    return False


def needs_synthesis_retry(
    answer: str,
    supplier_name: str = "",
    tools_used: list[str] | None = None,
    raw_tool_results: list[tuple[str, dict]] | None = None,
) -> bool:
    if not (answer or "").strip():
        return False
    if has_unsupported_recommendation(answer) or misnames_product(answer, supplier_name):
        return True
    if has_vague_comparison(answer):
        return True
    if has_generic_recommendation(answer):
        return True
    if claims_unsupported_strong_decline(answer, raw_tool_results):
        return True
    if raw_tool_results:
        from app.services.currency_format import sanitize_answer_currency
        if sanitize_answer_currency(answer, raw_tool_results) != answer:
            return True
    return False
