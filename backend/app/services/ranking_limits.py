"""
Deterministic extraction and validation of top-N limits from Swedish ranking phrases.
"""

from __future__ import annotations

import re
from typing import Optional

DEFAULT_PRODUCT_RANKING_LIMIT = 5
YTD_PRODUCT_RANKING_LIMIT = 10
ALL_PRODUCTS_RANKING_LIMIT = 50
MIN_RANKING_LIMIT = 1
MAX_RANKING_LIMIT = 10

_NUMBER_WORDS: dict[str, int] = {
    "en": 1,
    "ett": 1,
    "två": 2,
    "tva": 2,
    "tre": 3,
    "fyra": 4,
    "fem": 5,
    "sex": 6,
    "sju": 7,
    "åtta": 8,
    "atta": 8,
    "nio": 9,
    "tio": 10,
}

_WORD_ALT = "|".join(re.escape(w) for w in _NUMBER_WORDS)


def clamp_ranking_limit(value: int, *, allow_large: bool = False) -> int:
    """Clamp ranking limit to safe bounds (1–10, or up to 50 for all-products mode)."""
    upper = 50 if allow_large else MAX_RANKING_LIMIT
    return max(MIN_RANKING_LIMIT, min(int(value), upper))


def extract_ranking_limit(message: str) -> Optional[int]:
    """
    Extract an explicit top-N from Swedish ranking phrases.

    Returns None when no number is requested.
    """
    msg = (message or "").strip().lower()
    if not msg:
        return None

    m = re.search(r"\b(?:top|topp)\s*(\d+)\b", msg, re.IGNORECASE)
    if m:
        return clamp_ranking_limit(int(m.group(1)))

    m = re.search(r"\bvisa\s+(\d+)\s+produkter?\b", msg, re.IGNORECASE)
    if m:
        return clamp_ranking_limit(int(m.group(1)))

    m = re.search(
        r"\b(?:vilka\s+(?:är\s+)?)?de\s+(\d+)\s+(?:bästa|största)\b",
        msg,
        re.IGNORECASE,
    )
    if m:
        return clamp_ranking_limit(int(m.group(1)))

    m = re.search(
        r"\b(\d+)\s+(?:bästa|största|mest\s+sålda)\s+(?:produkter?|produkt)\b",
        msg,
        re.IGNORECASE,
    )
    if m:
        return clamp_ranking_limit(int(m.group(1)))

    m = re.search(
        rf"\b(?:de\s+)?({_WORD_ALT})\s+(?:bästa|största|mest\s+sålda)\b",
        msg,
        re.IGNORECASE,
    )
    if m:
        return clamp_ranking_limit(_NUMBER_WORDS[m.group(1).lower()])

    m = re.search(
        rf"\b({_WORD_ALT})\s+bästa\s+produkter?\b",
        msg,
        re.IGNORECASE,
    )
    if m:
        return clamp_ranking_limit(_NUMBER_WORDS[m.group(1).lower()])

    return None


_LOW_REVENUE_RANKING_RE = re.compile(
    r"("
    r"(lägst|minst).{0,40}(omsättning|försäljning|intäkt)|"
    r"(omsättning|försäljning|intäkt).{0,40}(lägst|minst)|"
    r"sämst.{0,30}(omsättning|försäljning|säljer|sålt)|"
    r"produkter?.{0,40}sämst"
    r")",
    re.IGNORECASE | re.DOTALL,
)

ASCENDING_PRODUCT_RANKING_TITLE = "Produkter med lägst omsättning"


def is_ascending_product_ranking_question(message: str) -> bool:
    """True for low-revenue / ascending product ranking (not product decline)."""
    msg = (message or "").strip()
    if not msg:
        return False
    return bool(_LOW_REVENUE_RANKING_RE.search(msg))


def resolve_product_ranking_limit(
    message: str,
    *,
    plan_limit: Optional[int] = None,
    is_ytd: bool = False,
    all_products: bool = False,
) -> int:
    """
    Resolve the final get_top_products limit.

    Priority: explicit phrase in message → validated planner limit → default.
    """
    if all_products:
        return clamp_ranking_limit(ALL_PRODUCTS_RANKING_LIMIT, allow_large=True)

    explicit = extract_ranking_limit(message)
    if explicit is not None:
        return explicit

    if plan_limit is not None:
        return clamp_ranking_limit(plan_limit)

    if is_ytd:
        return YTD_PRODUCT_RANKING_LIMIT
    return DEFAULT_PRODUCT_RANKING_LIMIT
