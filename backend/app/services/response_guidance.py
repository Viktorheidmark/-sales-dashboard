"""
Executive response-writing guidance for chat synthesis.

Kept separate from orchestration so prompts stay maintainable and testable.
"""

from __future__ import annotations

import re

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
    r"identifiera potentiella)",
    re.IGNORECASE,
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
- Inkludera: leverantörens andel, övriga aktörers andel, kategori.
- Skriv "Övriga aktörer" — nämn inte antal konkurrenter eller "en aktör".
- Avsluta utan rekommendation — ingen uppföljning om produkter, marknadsföring eller strategier.
"""

    if "get_top_products" in tools or (_TOP_PRODUCTS_RE.search(q) and "nedgång" not in q.lower()):
        return """
FRÅGETYP: Topprodukter
- Första meningen: tydlig vinnare med exakt product_name.
- Andra meningen: tvåa (runner-up) med exakt product_name.
- Valfri tredje mening: en kort faktainlação (t.ex. att de två står för största delen av omsättningen).
- Avsluta utan rekommendation — ingen marknadsföring, kampanj, prissättning, lager eller distribution.
- Förbjudet: "överväg att fokusera på marknadsföring" och liknande råd.
- Lista inte fler än två produkter i text; diagrammet visar resten.
"""

    if "get_declining_products" in tools or _DECLINING_RE.search(q):
        return """
FRÅGETYP: Produkter i nedgång
- Börja med största nedgången med exakt product_name, procent och omsättningsförändring.
- Ignorera produkter med marginell förändring.
- Avsluta med högst ett specifikt uppföljningssteg som produkten stödjer, t.ex.:
  "Jämför produkten mellan regioner." / "Följ utvecklingen mot föregående period."
- Inga antaganden om pris, lager, kampanj eller marknadsföring.
"""

    if "get_sales_over_time" in tools and _WEEKLY_SALES_RE.search(q):
        return f"""
FRÅGETYP: Senaste avslutade veckan
- Börja med exakt period från completed_week_label i verktygsresultat, eller date_range om etiketten saknas
  (t.ex. "Senaste avslutade vecka: 16–22 juni 2026").
- Ange omsättning, antal ordrar och sålda enheter för den veckan (från serien).
- En kort observation — t.ex. jämförelse mot föregående fullständiga vecka om data finns.
- Nämn leverantören ("{name}") en gång.
- Ingen rekommendation och ingen uppmaning att analysera längre perioder.
- Om completed_week_label finns: skriv inte lång förklaring om ofullständig pågående vecka (notis visas under diagrammet).
"""

    if "get_sales_over_time" in tools or _TREND_RE.search(q):
        return f"""
FRÅGETYP: Försäljningstrend
- Nämn leverantören ("{name}") minst en gång.
- Ange den faktiska perioden från date_range i verktygsresultat.
- Beskriv övergripande riktning utifrån fullständiga perioder — ingen månad-för-månad- eller dag-för-dag-lista
  om användaren inte bett om det.
- För cirka 15–90 dagar: beskriv veckovis utveckling (inte dag-för-dag).
- För över 90 dagar: beskriv månadsvis utveckling.
- Om analysis_note eller completed_week_label finns: nämn INTE ofullständig period i brödtexten (notis under diagrammet).
- Dra inga slutsatser om kraftig nedgång från ofullständig period.
- Ingen avslutande rekommendation, uppföljning eller "överväg att analysera".
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
    if raw_tool_results:
        from app.services.currency_format import sanitize_answer_currency
        if sanitize_answer_currency(answer, raw_tool_results) != answer:
            return True
    name = (supplier_name or "").strip()
    if name and tools_used and "get_sales_over_time" in tools_used:
        if name.lower() not in answer.lower():
            return True
    return False
