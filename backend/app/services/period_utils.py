"""
Shared incomplete-period handling for sales-over-time series.

Mirrors the dashboard SalesTrend chart policy: exclude the current
incomplete day/week/month bucket from trend analysis when a completed
history exists.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

_INCOMPLETE_LABELS = {"day": "dag", "week": "vecka", "month": "månad"}

_MONTHS_SV = (
    "januari", "februari", "mars", "april", "maj", "juni",
    "juli", "augusti", "september", "oktober", "november", "december",
)


def completed_week_bounds(reference: Optional[date] = None) -> tuple[date, date]:
    """Monday–Sunday of the most recent fully completed ISO week."""
    today = reference or datetime.now(tz=timezone.utc).date()
    current_monday = today - timedelta(days=today.weekday())
    last_sunday = current_monday - timedelta(days=1)
    last_monday = last_sunday - timedelta(days=6)
    return last_monday, last_sunday


def format_week_range_sv(week_monday: date | str) -> str:
    if isinstance(week_monday, str):
        week_monday = date.fromisoformat(week_monday[:10])
    sunday = week_monday + timedelta(days=6)

    def part(d: date) -> str:
        return f"{d.day} {_MONTHS_SV[d.month - 1]}"

    if week_monday.year == sunday.year and week_monday.month == sunday.month:
        return f"{week_monday.day}–{sunday.day} {_MONTHS_SV[sunday.month - 1]} {sunday.year}"
    if week_monday.year == sunday.year:
        return f"{part(week_monday)}–{part(sunday)} {sunday.year}"
    return f"{part(week_monday)} {week_monday.year}–{part(sunday)} {sunday.year}"


def completed_week_label(week_monday: date | str) -> str:
    return f"Senaste avslutade vecka: {format_week_range_sv(week_monday)}"


def current_period_start(granularity: str, reference: Optional[date] = None) -> str:
    today = reference or datetime.now(tz=timezone.utc).date()
    if granularity == "week":
        monday = today - timedelta(days=today.weekday())
        return monday.isoformat()
    if granularity == "month":
        return today.replace(day=1).isoformat()
    return today.isoformat()


def series_date_range(series: list[dict], granularity: str) -> Optional[dict[str, str]]:
    if not series:
        return None
    start = str(series[0].get("period", ""))[:10]
    end_period = str(series[-1].get("period", ""))[:10]
    if not start or not end_period:
        return None
    end_d = date.fromisoformat(end_period)
    if granularity == "week":
        end_d = end_d + timedelta(days=6)
    elif granularity == "month":
        next_month = (end_d.replace(day=28) + timedelta(days=4)).replace(day=1)
        end_d = next_month - timedelta(days=1)
    return {"start": start, "end": end_d.isoformat()}


def filter_incomplete_series(
    series: list[dict],
    granularity: str,
    reference: Optional[date] = None,
) -> tuple[list[dict], dict]:
    """
    Return (completed_series, metadata).

    metadata may include:
      - excluded_incomplete_period: bool
      - incomplete_period_start: str
      - completed_week_label: str (Swedish, for weekly synthesis)
      - analysis_note: str (Swedish, for synthesis — omitted for weekly when compact label suffices)
    """
    if not series:
        return [], {}

    period_start = current_period_start(granularity, reference)
    completed = [p for p in series if str(p.get("period", "")) < period_start]
    has_incomplete_tail = len(completed) < len(series)

    if has_incomplete_tail and completed:
        if granularity == "week":
            last_week = str(completed[-1].get("period", ""))[:10]
            return completed, {
                "excluded_incomplete_period": True,
                "incomplete_period_start": period_start,
                "completed_week_label": completed_week_label(last_week),
            }

        label = _INCOMPLETE_LABELS.get(granularity, granularity)
        note = (
            f"Pågående {label} (från {period_start}) är ofullständig och har exkluderats från trendanalys. "
            "Jämför inte den ofullständiga perioden mot fullständiga tidigare perioder och "
            "dra inga slutsatser om nedgång enbart utifrån den."
        )
        return completed, {
            "excluded_incomplete_period": True,
            "incomplete_period_start": period_start,
            "analysis_note": note,
        }

    if not completed and series:
        last_period = str(series[-1].get("period", ""))
        if last_period >= period_start:
            label = _INCOMPLETE_LABELS.get(granularity, granularity)
            note = (
                f"Endast pågående {label} finns i serien — ingen fullständig jämförelseperiod "
                "är tillgänglig ännu. Beskriv inte trend eller nedgång."
            )
            return series, {
                "excluded_incomplete_period": False,
                "incomplete_period_start": period_start,
                "analysis_note": note,
            }

    meta: dict = {}
    if granularity == "week" and completed:
        last_week = str(completed[-1].get("period", ""))[:10]
        meta["completed_week_label"] = completed_week_label(last_week)

    return (completed if completed else series), meta


def apply_sales_over_time_period_policy(result: dict) -> dict:
    """Return a copy of an MCP sales-over-time result with incomplete buckets handled."""
    if not isinstance(result, dict):
        return result

    series = result.get("series") or []
    granularity = result.get("granularity", "month")
    completed, meta = filter_incomplete_series(series, granularity)

    out = dict(result)
    out["series"] = completed
    aligned = series_date_range(completed, granularity)
    if aligned:
        out["date_range"] = aligned

    if meta:
        out["period_analysis"] = meta
        if meta.get("completed_week_label"):
            out["completed_week_label"] = meta["completed_week_label"]
        if meta.get("analysis_note"):
            out["analysis_note"] = meta["analysis_note"]
            limitations = list(result.get("limitations") or [])
            if meta["analysis_note"] not in limitations:
                limitations.append(meta["analysis_note"])
            out["limitations"] = limitations
    return out
