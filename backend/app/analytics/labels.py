"""
Shared human-readable Swedish period labels for UI-facing surfaces.

Used by the chart builder, responder, and orchestrator payload so that chart
axis labels, subtitles, chips, footers, and saved-insight display never show raw
ISO dates. Raw ISO is kept only in machine fields (``period_a``/``period_b``),
API payloads, logs, and debug metadata.
"""

from __future__ import annotations

from app.analytics.schemas import DateRange
from app.services.period_utils import format_date_range_sv


def readable_range(period: DateRange) -> str:
    """A readable Swedish label for a period.

    Prefers a human label the planner already attached (e.g. ``"mars 2026"`` or
    ``"senaste 30 dagarna"``); otherwise formats the exact range in Swedish
    (e.g. ``"1–22 maj 2026"``). Never returns a raw ISO range.
    """
    if period.label:
        return period.label
    return format_date_range_sv(period.start.isoformat(), period.end.isoformat())
