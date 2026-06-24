"""
Executive response-writing guidance for chat synthesis.

Kept separate from orchestration so prompts stay maintainable and testable.
"""

from __future__ import annotations

import re

from app.services.intent_router import is_diagram_followup_request

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
- Struktur: 1) en mening slutsats 2) 2–3 kompakta fakta 3) högst ett datastött nästa steg.
- Börja direkt med slutsatsen — inga inledningar som "Under perioden ... har ... utvecklats enligt följande".
- Använd "{name}" endast när du syftar på leverantören/företaget — inte "ert märke" om inte användaren skrev det.
- PRODUKTNAMN: kopiera exakt product_name från verktygsresultat. Sätt ALDRIG leverantörsnamnet framför produktnamnet
  om det inte redan ingår i product_name (t.ex. skriv "Arla Iced Coffee Latte", INTE "{name} Iced Coffee Latte").
- Omsättning: använd VALUTAREFERENS och VALUTAFORMAT — under 1 000 kr, 1 000–999 999 tkr, från 1 000 000 mkr.
  Exempel: 75 619 SEK = 75,6 tkr (ALDRIG mkr). 1 200 000 SEK = 1,2 mkr.
- Max cirka 90 ord om inte användaren uttryckligen ber om detaljer.
- Undvik AI-fraser och utfyllnad. Inga stycken som bara sammanfattar det du redan sagt.
- Rekommendera INTE marknadsföring, prissättning, kampanjer, lager, distribution eller kundpreferenser
  om datan inte explicit innehåller dessa dimensioner.
- Avsluta INTE med generiska råd ("för att fortsätta...", "kan det vara fördelaktigt att analysera...").
  Uppföljning sker via knappar i gränssnittet — skriv bara fakta från verktygsdata.
- Vid periodjämförelse: ange alltid exakt jämförelsebas (datumintervall eller antal dagar).
  Skriv ALDRIG bara "föregående period", "tidigare period" eller "jämfört med tidigare" utan exakt period.
- Förbjudna fraser och liknande: {forbidden}.

EXEMPEL PÅ BRA TON:
- "{name} har 69,2 % marknadsandel i Mejeri."
- "KESO Cottage Cheese är största produkten i Stockholm med 7,1 tkr i omsättning."
- "Arla Iced Coffee Latte är största risken: omsättningen är ned 56,5 % mot föregående 30 dagar."
- "Jämför Arla Iced Coffee Latte mellan regioner för att se om tappet är koncentrerat."
"""


def synthesis_blueprint(question: str, tools_used: list[str], supplier_name: str = "") -> str:
    q = question.strip()
    tools = set(tools_used)
    name = supplier_name.strip() or "leverantören"

    if "get_market_share" in tools or _MARKET_SHARE_RE.search(q):
        return """
FRÅGETYP: Marknadsandel
- Max 3 korta meningar.
- Första meningen MÅSTE nämna kategori OCH analyserad tidsperiod (enligt OBLIGATORISK PERIOD I SVARET).
- Inkludera: leverantörens andel, övriga aktörers andel.
- Skriv "Övriga aktörer" — nämn inte antal konkurrenter eller "en aktör".
- Avsluta utan rekommendation — ingen uppföljning om produkter, marknadsföring eller strategier.
"""

    if "get_supplier_kpis" in tools:
        return f"""
FRÅGETYP: Översikt (KPI)
- Första meningen MÅSTE ange analyserad tidsperiod (period_label_opening / period_label_answer).
- Slutsats om omsättning för analyserad period (date_range i verktygsresultat).
- Andra meningen: förändring i ordrar och enheter om relevant.
- Tredje meningen: procentuell förändring mot jämförelsebas — använd OBLIGATORISK JÄMFÖRELSETEXT
  från JÄMFÖRELSE- OCH PERIODKRAV ordagrant (t.ex. "jämfört med samma period föregående år, 1 januari–23 juni 2025").
- Nämn leverantören ("{name}") en gång.
- Max 3 meningar. INGEN rekommendation eller generisk uppmaning att analysera vidare.
"""

    if "get_top_products" in tools or (_TOP_PRODUCTS_RE.search(q) and "nedgång" not in q.lower()):
        return """
FRÅGETYP: Topprodukter
- Första meningen MÅSTE tydligt ange analyserad tidsperiod (period_label_opening / period_label_answer).
- Nämn tydlig vinnare med exakt product_name och region om den finns i verktygsresultat.
- Andra meningen: tvåa (runner-up) med exakt product_name om den finns i verktygsresultat.
- Nämn ENDAST produkter som finns i verktygsresultat — aldrig fler än requested_limit.
- Om färre än tre produkter returnerades: lista bara dessa, utan att hitta på fler.
- Avsluta utan rekommendation — ingen marknadsföring, kampanj, prissättning, lager eller distribution.
- Förbjudet: "överväg att fokusera på marknadsföring" och liknande råd.
"""

    if "get_revenue_drivers" in tools:
        return """
FRÅGETYP: Omsättningsutveckling (30 dagar)
- Börja med total omsättningsförändring mellan senaste och föregående 30-dagarsperiod (absolut och %).
- Nämn ordrar och enheter om de förstärker bilden.
- Lyft största positiva produktbidrag och största negativa produktbidrag med exakta product_name.
- Nämn region med starkast respektive svagast förändring om datan finns.
- Max 4 korta meningar. Ingen rekommendation.
"""

    if "get_declining_products" in tools or _DECLINING_RE.search(q):
        return """
FRÅGETYP: Produkter i nedgång
- Första meningen MÅSTE ange analyserad tidsperiod (period_label_answer).
- Börja med största nedgången med exakt product_name, procent och omsättningsförändring.
- Ignorera produkter med marginell förändring.
- Avsluta med högst ett specifikt uppföljningssteg som produkten stödjer, t.ex.:
  "Jämför produkten mellan regioner." / "Följ utvecklingen mot föregående period."
- Inga antaganden om pris, lager, kampanj eller marknadsföring.
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
- Börja med exakt period från completed_week_label i verktygsresultat, eller date_range om etiketten saknas
  (t.ex. "Senaste avslutade vecka: 16–22 juni 2026").
- Ange omsättning, antal ordrar och sålda enheter för den veckan (från serien).
- En kort mening om jämförelse: om weekly_comparison_available är false eller comparison_note finns,
  avsluta med exakt comparison_note-texten (affärsspråk om saknad jämförelsevecka).
  Om två eller fler fullständiga veckor finns: en kort jämförelse mot föregående fullständiga vecka.
- Nämn leverantören ("{name}") en gång.
- Max cirka 60 ord. Ingen rekommendation.
- Nämn ALDRIG pågående vecka, serien, ofullständig period, exkludering eller intern databehandling.
"""

    if "get_sales_over_time" in tools or _TREND_RE.search(q):
        return f"""
FRÅGETYP: Försäljningstrend
- Nämn leverantören ("{name}") minst en gång.
- Första meningen MÅSTE ange analyserad tidsperiod (period_label_answer eller analysed_range_label).
- Ange den faktiska perioden från analysed_range_label eller date_range i verktygsresultat.
- Beskriv övergripande riktning utifrån fullständiga perioder — ingen månad-för-månad- eller dag-för-dag-lista
  om användaren inte bett om det.
- När du nämner enskilda veckor i serien: använd exakt period_label från varje datapunkt.
  Skriv aldrig "vecka" framför ett datumintervall — använd "veckan" endast när period_label börjar så.
- För cirka 15–90 dagar: beskriv veckovis utveckling (inte dag-för-dag).
- För över 90 dagar: beskriv månadsvis utveckling.
- TRENDSPRÅK: Använd "nedåtgående trend" endast vid tydlig och ihållande nedgång över jämförbara
  fullständiga perioder (minst två lägre veckor/månader efter toppen).
- Vid blandad utveckling: "Försäljningen varierade under perioden.",
  "De senaste avslutade veckorna låg lägre än slutet av maj.",
  "Utvecklingen är svagare jämfört med periodens topp."
- Dra aldrig slutsats om bred nedgång från en ofullständig gränsvecka.
- Om analysis_note eller completed_week_label finns: nämn INTE ofullständig period i brödtexten (notis under diagrammet).
- Dra inga slutsatser om kraftig nedgång från ofullständig period.
- Ingen avslutande rekommendation, uppföljning eller "överväg att analysera".
- Vid jämförelse mot annan period: ange exakt jämförelsebas — aldrig bara "föregående period".
"""

    if _FOCUS_RE.search(q):
        return """
FRÅGETYP: Fokus nästa period
- Kort prioritering: vilken produkt/kategori/region som sticker ut enligt data.
- Ge högst ETT konkret uppföljningssteg som finns i produkten, t.ex.:
  "Jämför produkten mellan regioner." / "Kontrollera om tappet är koncentrerat till Stockholm."
  / "Följ utvecklingen mot föregående period." / "Jämför produktens utveckling med övriga produkter i Mejeri."
- Inga numrerade listor med generiska åtgärder. Ingen marknadsföring, prissättning, lager eller kundpreferenser.
"""

    return """
FRÅGETYP: Allmän analys
- Slutsats först, sedan kompakta fakta. Ett nästa steg endast om datan stödjer det.
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
) -> str:
    if not answer or not raw_tool_results:
        return answer
    from app.services.comparison_labels import comparison_metadata

    meta = comparison_metadata(raw_tool_results)
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
    name = (supplier_name or "").strip()
    if name and tools_used and "get_sales_over_time" in tools_used:
        if name.lower() not in answer.lower():
            return True
    return False
