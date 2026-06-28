"""
Declining-product period resolution — clarification vs explicit comparison windows.
"""

from __future__ import annotations

import re
from datetime import date
from typing import TYPE_CHECKING, Any, Optional

from app.services.intent_router import ToolPlan
from app.services.period_labels import message_specifies_period
from app.services.period_utils import resolve_period_range

if TYPE_CHECKING:
    from app.services.intent_router import PriorTurnContext

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
_SEDAN_START_RE = re.compile(r"^sedan\s+start\s*$", re.IGNORECASE)

DECLINE_PERIOD_ACTION = "analyze_decline"

DECLINE_PERIOD_KIND_PHRASES: dict[str, str] = {
    "rolling_30": "senaste 30 dagarna",
    "rolling_90": "senaste 90 dagarna",
    "year_to_date": "i år",
    "full_history": "hela perioden",
}


def prior_awaiting_decline_period(prior: Optional["PriorTurnContext"]) -> bool:
    """True when the immediately previous turn is awaiting a decline-period choice."""
    if not prior or not prior.analysis_context:
        return False
    ac = prior.analysis_context
    return bool(
        ac.get("awaiting_decline_period")
        or ac.get("awaiting_clarification") == "decline_period"
    )


def _normalise_bare_period(message: str) -> str:
    """Convert bare 'N dagar' / 'N månader' → 'senaste N dagarna' so resolve_period_range handles it."""
    msg = message.strip()
    if _SEDAN_START_RE.match(msg):
        return "hela perioden"
    m = _BARE_DAYS_RE.match(msg)
    if m:
        return f"senaste {m.group(1)} dagarna"
    m = _BARE_MONTHS_RE.match(msg)
    if m:
        days = int(m.group(1)) * 30
        return f"senaste {days} dagarna"
    return msg


def plan_decline_period_from_action(follow_up_action: dict[str, Any]) -> list[ToolPlan]:
    """Structured decline-period selection from the in-chat composer."""
    if str(follow_up_action.get("action") or "").strip() != DECLINE_PERIOD_ACTION:
        return []
    ctx = follow_up_action.get("context") or {}
    if not isinstance(ctx, dict):
        return []
    period_kind = str(ctx.get("period_kind") or "").strip()
    if period_kind == "custom":
        start_s = str(ctx.get("start_date") or "").strip()
        end_s = str(ctx.get("end_date") or "").strip()
        if not start_s or not end_s:
            return []
        try:
            start = date.fromisoformat(start_s)
            end = date.fromisoformat(end_s)
        except ValueError:
            return []
        if end < start:
            return []
        days = (end - start).days + 1
        return [
            ToolPlan(
                tool_name="get_declining_products",
                args={
                    "days": min(days, 365),
                    "limit": 5,
                    "_period_kind": "custom",
                    "_period_explicit": True,
                    "start_date": start_s,
                    "end_date": end_s,
                },
                reason="decline period composer custom range",
            )
        ]
    phrase = DECLINE_PERIOD_KIND_PHRASES.get(period_kind)
    if not phrase:
        return []
    return [build_decline_tool_plan(phrase, reason="decline period composer")]


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
