"""
Declining-product period resolution — clarification vs explicit comparison windows.
"""

from __future__ import annotations

import re
from typing import Optional

from app.services.intent_router import ToolPlan
from app.services.period_labels import message_specifies_period
from app.services.period_utils import resolve_period_range

DECLINE_PERIOD_CLARIFICATION = (
    "Vilken period vill du jämföra? Du kan exempelvis skriva "
    '"senaste 30 dagarna", "i år" eller "senaste 12 månaderna".'
)

_DECLINE_VERB_RE = re.compile(r"tappat|minskat|nedgång|fallit|sjunk", re.IGNORECASE)
_DECLINE_RANKING_RE = re.compile(
    r"(vilken|vilket|vad).{0,40}(produkt|vara)|produkt.{0,30}(tappat|minskat|nedgång|fallit|sjunk)",
    re.IGNORECASE | re.DOTALL,
)


def is_decline_ranking_question(message: str) -> bool:
    """True for questions like 'Vilken produkt har tappat mest?'"""
    msg = (message or "").strip()
    if not msg or not _DECLINE_VERB_RE.search(msg):
        return False
    return bool(_DECLINE_RANKING_RE.search(msg))


def decline_question_needs_period(message: str) -> bool:
    return is_decline_ranking_question(message) and not message_specifies_period(message)


def build_decline_tool_plan(message: str, *, reason: str = "declining products") -> ToolPlan:
    period = resolve_period_range(message)
    days = int(period.get("days") or 30)
    period_kind = str(period.get("period_kind") or f"rolling_{days}")
    if period_kind == "current_year":
        period_kind = "year_to_date"
    return ToolPlan(
        tool_name="get_declining_products",
        args={
            "days": min(days, 365),
            "limit": 5,
            "_period_kind": period_kind,
            "_period_explicit": True,
        },
        reason=reason,
    )


_BARE_DAYS_RE = re.compile(r"^(\d+)\s*dag(?:ar)?\s*$", re.IGNORECASE)
_BARE_MONTHS_RE = re.compile(r"^(\d+)\s*m[åa]n(?:ader?)?\s*$", re.IGNORECASE)


def _normalise_bare_period(message: str) -> str:
    """Convert bare 'N dagar' / 'N månader' → 'senaste N dagarna' so resolve_period_range handles it."""
    msg = message.strip()
    m = _BARE_DAYS_RE.match(msg)
    if m:
        return f"senaste {m.group(1)} dagarna"
    m = _BARE_MONTHS_RE.match(msg)
    if m:
        days = int(m.group(1)) * 30
        return f"senaste {days} dagarna"
    return msg


def plan_awaiting_decline_period(message: str) -> list[ToolPlan]:
    """Continue decline analysis after period clarification."""
    normalised = _normalise_bare_period(message)
    if not message_specifies_period(normalised):
        return []
    return [build_decline_tool_plan(normalised, reason="decline period clarification follow-up")]


def decline_trend_subtitle(result: dict) -> str:
    """Subtitle for the primary decline trend chart."""
    days = int(result.get("comparison_days") or 30)
    period_kind = str(result.get("_period_kind") or "")
    if period_kind in ("year_to_date", "current_year"):
        return "Omsättning per vecka · jämförelse mellan föregående och innevarande år hittills"
    if days == 30 or period_kind == "rolling_30":
        return "Omsättning per vecka · jämförelse mellan föregående och senaste 30 dagar"
    if days >= 330 or period_kind in ("rolling_365", "rolling_year"):
        return "Omsättning per vecka · jämförelse mellan föregående och senaste 12 månaderna"
    return f"Omsättning per vecka · jämförelse mellan föregående och senaste {days} dagarna"
