"""
Deterministic guardrail layer — runs BEFORE any OpenAI or MCP call.

Classifications (in priority order):
  1. prompt_injection  — attempts to hijack instructions or expose internals
  2. restricted        — competitor detail queries (aggregate-only policy)
  3. insufficient_data — metrics not available in the data model
  4. unsupported       — completely off-topic questions
  5. clarification_needed — too vague to route to a tool
  6. supported         — normal analytics questions → pass through to LLM+MCP
"""

import re
from dataclasses import dataclass, field


@dataclass
class GuardrailResult:
    classification: str
    answer: str
    limitations: list[str]
    should_call_llm: bool
    should_call_mcp: bool


# ---------------------------------------------------------------------------
# Pattern sets — compiled once at import time
# ---------------------------------------------------------------------------

_INJECTION_PHRASES = [
    r"ignore\s+(previous|prior|all|the)\s+(instructions?|prompts?|rules?|constraints?)",
    r"disregard\s+(previous|prior|all|the)\s+(instructions?|prompts?|rules?)",
    r"forget\s+(previous|prior|all|the|your)\s+(instructions?|prompts?|rules?|training)",
    r"you\s+are\s+now\s+(a|an|acting\s+as)",
    r"pretend\s+(you\s+are|to\s+be)",
    r"act\s+as\s+(if\s+you\s+(are|were)|a\s+different)",
    r"new\s+(persona|role|character|instructions?)",
    r"(reveal|show|print|display|output|give\s+me|tell\s+me|what\s+is)\s+(the\s+)?(system\s+prompt|system\s+message|hidden\s+instructions?|internal\s+prompt)",
    r"(reveal|show|expose|leak|dump|print|output)\s+(the\s+)?(jwt|json\s+web\s+token|secret\s+key|api\s+key|private\s+key|credentials?|password|\.env|env\s+file|environment\s+variables?|config)",
    r"\bjwt\b.{0,40}(secret|key|token|payload|content)",
    r"(what|tell\s+me|show\s+me|give\s+me).{0,30}\bjwt\b",
    r"(show|reveal|print|output|give\s+me)\s+(the\s+)?(database\s+(url|connection|password|credentials?)|db\s+(url|password|credentials?))",
    r"(run|execute|perform)\s+(raw\s+)?(sql|database\s+quer(y|ies))",
    r"(select|insert|update|delete|drop|alter|create)\s+.{0,30}\s+(from|into|table|database)",
    r"do\s+not\s+use\s+(mcp|the\s+tools?|tool\s+calls?)",
    r"bypass\s+(the\s+)?(tools?|mcp|guardrails?|filters?|restrictions?)",
    r"(what|tell\s+me|show\s+me).{0,30}(source\s+code|implementation|how\s+you\s+(work|are\s+built|are\s+implemented))",
    r"(print|output|reveal|show)\s+(the\s+)?(server|file|directory|path|/\w)",
    r"mcp\s+(schema|implementation|server|protocol)\s+(detail|config|secret)",
    r"supplier_id\s*(=|:|\s+is)\s*['\"]?[0-9a-f\-]{8,}",
    r"(change|set|override|modify)\s+(my\s+)?supplier",
]

_INJECTION_RE = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _INJECTION_PHRASES]


_RESTRICTED_PHRASES = [
    r"konkurrent.{0,30}(kund(er|lista|information)?|order(er|historia)?|produkt(er|katalog|detaljer)?|kontakt|namn)",
    r"(kund(er|information|lista|namn)|kontakter).{0,30}konkurrent",
    r"competitor.{0,30}(customer|order|product\s+detail|contact|name|list)",
    r"(customer|order).{0,30}competitor",
    r"(vilka|lista|visa|ge\s+mig).{0,30}(konkurrenters?)\s+(kunder|ordrar|produkter|kontakter)",
    r"(who\s+are|list|show\s+me).{0,30}(competitor.{0,10})(customers|orders|products|contacts)",
    r"(köpare|inköpare|återförsäljare).{0,30}konkurrent",
]

_RESTRICTED_RE = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _RESTRICTED_PHRASES]


_INSUFFICIENT_PHRASES = [
    r"(marginal|bruttomarginal|nettomarginal|vinstmarginal)",
    r"\b(vinst|nettoresultat|rörelseresultat|ebitda|ebit)\b",
    r"(lagersaldo|lagerbalans|lagernivå|inventory|stock\s+level)",
    r"\b(retur(er)?|återsändning(ar)?|reklamation(er)?|returns?|refund)\b",
    r"(prognos|forecast|predikt|predict)",
    r"\b(kampanjkostnad|marknadsföringskostnad|reklambud|ad\s+spend|campaign\s+spend)\b",
    r"\b(inköpspris|kostnad\s+per\s+enhet|cost\s+of\s+goods|cogs)\b",
    r"\b(kundnöjdhet|nps|net\s+promoter|kundbetyg|customer\s+satisfaction)\b",
    r"\b(klickfrekvens|konverteringsgrad|ctr|conversion\s+rate)\b",
]

_INSUFFICIENT_RE = [re.compile(p, re.IGNORECASE) for p in _INSUFFICIENT_PHRASES]

_INVENTORY_RE = re.compile(
    r"(lagersaldo|lagerbalans|lagernivå|inventory|stock\s+level|hur\s+mycket\s+lager)",
    re.IGNORECASE,
)


_UNSUPPORTED_PHRASES = [
    r"(vädr?e?t\b|vädret|väderlek|väderprognos|temperatur|weather|forecast.{0,10}weather)",
    r"\b(nyheter|news|headlines?|aktuella\s+händelser|current\s+events?)\b",
    r"\b(sport|fotboll|hockey|tennis|basket|resultat.{0,10}(match|spel|serie))\b",
    r"\b(recept|matlagning|kock|cooking|recipe)\b",
    r"\b(aktiekurs|börsen?|aktiepris|stock\s+price|share\s+price|crypto|bitcoin|ethereum)\b",
    r"\b(skriv\s+(en|ett|kod)|koda|programmera|debug\s+my\s+code)\b",
    r"write\s+(me\s+)?(a\s+)?(\w+\s+)?(function|code|script|program|class|method)\b",
    r"\b(translate|översätt|übersetz|traduire)\b",
    r"\b(musik|låt|artist|spotify|playlist)\b",
    r"\b(film|serie|netflix|hbo|tv.?show)\b",
    r"\b(juridik|lag|lagstiftning|legal\s+advice|law\s+question)\b",
    r"\b(hälsa|medicin|diagnos|symptom|läkare|health\s+advice|medical)\b",
]

_UNSUPPORTED_RE = [re.compile(p, re.IGNORECASE) for p in _UNSUPPORTED_PHRASES]


# Analytics keywords that confirm the question IS about sales data
_ANALYTICS_SIGNALS = re.compile(
    r"\b(försäljning|omsättning|intäkt|revenue|sales|produkt|producter|topp|bäst|sämst|"
    r"region|marknad|marknadsandel|market\s+share|trend|tillväxt|growth|kpi|periode?|"
    r"kvartal|månads?|vecko|dag|år|kategori|kaffe|snacks|hushåll|household|"
    r"minskning|declining|tappa|ökad|ökande|region|butik|store|channel)\b",
    re.IGNORECASE,
)

# Vague standalone words that likely need clarification
_VAGUE_ONLY = re.compile(
    r"^(hur\s+går\s+det|hur\s+ser\s+det\s+ut|berätta|vad\s+händer|vad\s+tycker\s+du|"
    r"something|anything|help|hjälp|info|information|tell\s+me\s+something|show\s+me\s+something|"
    r"what\s+do\s+you\s+think|vad\s+tänker\s+du)\s*\??$",
    re.IGNORECASE,
)

_CONVERSATIONAL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^hej\b", re.IGNORECASE), "Hej! Vad vill du analysera i försäljningen?"),
    (re.compile(r"^hejsan\b", re.IGNORECASE), "Hej! Vad vill du analysera i försäljningen?"),
    (re.compile(r"^hallå\b", re.IGNORECASE), "Hej! Vad vill du analysera i försäljningen?"),
    (re.compile(r"^tack\b", re.IGNORECASE), "Tack! Vad vill du titta närmare på?"),
    (re.compile(r"^okej\b", re.IGNORECASE), "Okej. Vad vill du analysera?"),
    (re.compile(r"^ok\b", re.IGNORECASE), "Okej. Vad vill du analysera?"),
    (re.compile(r"^bra\b", re.IGNORECASE), "Bra. Vad vill du titta närmare på?"),
    (re.compile(r"^(toppen|perfekt|kul)\b", re.IGNORECASE), "Bra. Vad vill du analysera?"),
    (
        re.compile(r"^vad kan du (hjälpa|göra)", re.IGNORECASE),
        "Jag kan hjälpa dig analysera försäljning, produkter, regioner och marknadsandel.",
    ),
    (
        re.compile(r"^hur kan du hjälpa", re.IGNORECASE),
        "Jag kan hjälpa dig analysera försäljning, produkter, regioner och marknadsandel.",
    ),
]


def conversational_reply(message: str) -> str | None:
    """Short neutral reply for greetings and capability questions."""
    msg = message.strip()
    for pattern, reply in _CONVERSATIONAL_PATTERNS:
        if pattern.search(msg):
            return reply
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify(message: str) -> GuardrailResult:
    """
    Classify an incoming chat message deterministically.
    No LLM involved — pure pattern matching.
    """
    msg = message.strip()

    # 1. Prompt injection — highest priority
    for pattern in _INJECTION_RE:
        if pattern.search(msg):
            return GuardrailResult(
                classification="prompt_injection",
                answer=(
                    "Det verkar som att din fråga försöker påverka hur systemet fungerar "
                    "eller komma åt intern information. Det är inte tillåtet. "
                    "Ställ gärna en fråga om er försäljningsdata istället."
                ),
                limitations=["Frågan nekades av säkerhetsskäl."],
                should_call_llm=False,
                should_call_mcp=False,
            )

    # 2. Restricted — competitor detail (not aggregate)
    for pattern in _RESTRICTED_RE:
        if pattern.search(msg):
            return GuardrailResult(
                classification="restricted",
                answer=(
                    "Konkurrentdata är tillgänglig i aggregerad form (t.ex. marknadsandel per kategori), "
                    "men detaljerad information om enskilda konkurrenters kunder, ordrar eller produkter "
                    "är inte tillgänglig i systemet. "
                    "Fråga gärna om er egen marknadsandel eller hur ni presterar i en viss kategori."
                ),
                limitations=["Konkurrentdata visas enbart aggregerat."],
                should_call_llm=False,
                should_call_mcp=False,
            )

    # 3. Insufficient data — metrics not in the data model
    if _INVENTORY_RE.search(msg):
        return GuardrailResult(
            classification="insufficient_data",
            answer=(
                "Jag har ingen lagerdata i den här demon, så jag kan inte bedöma lagersaldo. "
                "Jag kan däremot visa vilka produkter som säljer snabbast eller vilka som tappat mest."
            ),
            limitations=[],
            should_call_llm=False,
            should_call_mcp=False,
        )

    for pattern in _INSUFFICIENT_RE:
        if pattern.search(msg):
            return GuardrailResult(
                classification="insufficient_data",
                answer=(
                    "Jag har tyvärr inte den typen av data i systemet. "
                    "Tillgängligt är omsättning, ordrar, sålda enheter, produktranking, "
                    "regional försäljning och marknadsandel per kategori. "
                    "Vad vill du att jag tittar på istället?"
                ),
                limitations=["Efterfrågade mätvärden finns inte i datakällan."],
                should_call_llm=False,
                should_call_mcp=False,
            )

    # 4. Unsupported — off-topic
    for pattern in _UNSUPPORTED_RE:
        if pattern.search(msg):
            return GuardrailResult(
                classification="unsupported",
                answer=(
                    "Det är utanför vad jag kan hjälpa med. Jag är specialiserad på "
                    "er försäljningsanalys — fråga mig gärna om omsättning, produktprestanda, "
                    "regionala trender eller marknadsandel."
                ),
                limitations=[],
                should_call_llm=False,
                should_call_mcp=False,
            )

    # 5. Conversational — greetings, thanks, capability questions
    conv = conversational_reply(msg)
    if conv:
        return GuardrailResult(
            classification="conversational",
            answer=conv,
            limitations=[],
            should_call_llm=False,
            should_call_mcp=False,
        )

    # 6. Clarification needed — vague with no analytics signal
    if _VAGUE_ONLY.match(msg) and not _ANALYTICS_SIGNALS.search(msg):
        return GuardrailResult(
            classification="clarification_needed",
            answer=(
                "Jag behöver lite mer information för att kunna hjälpa dig. "
                "Vad vill du veta? Här är några exempel:\n\n"
                "- Hur ser vår försäljningstrend ut de senaste 90 dagarna?\n"
                "- Vilka produkter tappar mest i försäljning?\n"
                "- Hur stor är vår marknadsandel i Mejeri?\n"
                "- Vilka regioner presterar bäst?"
            ),
            limitations=[],
            should_call_llm=False,
            should_call_mcp=False,
        )

    # 7. Supported — pass through to LLM + MCP
    return GuardrailResult(
        classification="supported",
        answer="",
        limitations=[],
        should_call_llm=True,
        should_call_mcp=True,
    )
