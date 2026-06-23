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

WEEKLY_COMPARISON_UNAVAILABLE_NOTE = (
    "Det finns inte tillräckligt med jämförbar veckodata i den valda perioden "
    "för att bedöma utvecklingen mot föregående vecka."
)

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


def is_partial_start_week(week_monday: date | str, query_start: date) -> bool:
    """True when the query begins mid-week inside this bucket."""
    if isinstance(week_monday, str):
        week_monday = date.fromisoformat(week_monday[:10])
    return query_start > week_monday


def first_complete_week_monday(query_start: date) -> date:
    """First ISO Monday on or after query_start (for aligned MCP query bounds)."""
    if query_start.weekday() == 0:
        return query_start
    return query_start + timedelta(days=7 - query_start.weekday())


def align_weekly_query_bounds(
    start_date: str,
    end_date: str,
    reference: Optional[date] = None,
) -> dict[str, str]:
    """Snap weekly queries to complete ISO weeks ending at the latest completed Sunday."""
    ref = reference or datetime.now(tz=timezone.utc).date()
    start_d = date.fromisoformat(start_date[:10])
    end_d = date.fromisoformat(end_date[:10])
    _, completed_end = completed_week_bounds(ref)
    if end_d > completed_end:
        end_d = completed_end
    start_d = first_complete_week_monday(start_d)
    if start_d > end_d:
        start_d = end_d - timedelta(days=end_d.weekday())
    return {"start": start_d.isoformat(), "end": end_d.isoformat()}


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


def format_date_sv(d: date | str) -> str:
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    return f"{d.day} {_MONTHS_SV[d.month - 1]} {d.year}"


def format_date_range_sv(start: str, end: str) -> str:
    start_d = date.fromisoformat(start[:10])
    end_d = date.fromisoformat(end[:10])

    def part(d: date) -> str:
        return f"{d.day} {_MONTHS_SV[d.month - 1]}"

    if start_d.year == end_d.year and start_d.month == end_d.month:
        return f"{start_d.day}–{end_d.day} {_MONTHS_SV[end_d.month - 1]} {end_d.year}"
    if start_d.year == end_d.year:
        return f"{part(start_d)}–{part(end_d)} {end_d.year}"
    return f"{part(start_d)} {start_d.year}–{part(end_d)} {end_d.year}"


def completed_week_label(week_monday: date | str) -> str:
    return f"Senaste avslutade vecka: {format_week_range_sv(week_monday)}"


def analysed_weekly_range_label(start: str, end: str) -> str:
    return f"Analyserad period: {format_date_range_sv(start, end)}"


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


def _drop_partial_start_weeks(
    series: list[dict],
    query_start: Optional[str],
) -> tuple[list[dict], bool]:
    if not series or not query_start:
        return series, False
    qs = date.fromisoformat(query_start[:10])
    filtered = [
        p for p in series
        if not is_partial_start_week(str(p.get("period", ""))[:10], qs)
    ]
    return filtered, len(filtered) < len(series)


def filter_incomplete_series(
    series: list[dict],
    granularity: str,
    reference: Optional[date] = None,
    query_start: Optional[str] = None,
) -> tuple[list[dict], dict]:
    """
    Return (completed_series, metadata).

    metadata may include:
      - excluded_incomplete_period: bool
      - excluded_partial_start_week: bool
      - incomplete_period_start: str
      - completed_week_label: str (Swedish, for weekly synthesis)
      - analysed_range_label: str (Swedish, actual complete-week span)
      - analysis_note: str (Swedish, for synthesis — omitted for weekly when compact label suffices)
    """
    if not series:
        return [], {}

    meta: dict = {}
    working = list(series)

    if granularity == "week" and query_start:
        working, dropped_partial = _drop_partial_start_weeks(working, query_start)
        if dropped_partial:
            meta["excluded_partial_start_week"] = True

    period_start = current_period_start(granularity, reference)
    completed = [p for p in working if str(p.get("period", "")) < period_start]
    has_incomplete_tail = len(completed) < len(working)

    if has_incomplete_tail and completed:
        if granularity == "week":
            last_week = str(completed[-1].get("period", ""))[:10]
            meta.update({
                "excluded_incomplete_period": True,
                "incomplete_period_start": period_start,
                "completed_week_label": completed_week_label(last_week),
            })
            aligned = series_date_range(completed, granularity)
            if aligned:
                meta["analysed_range_label"] = analysed_weekly_range_label(
                    aligned["start"], aligned["end"],
                )
            if len(completed) < 2:
                meta["weekly_comparison_available"] = False
                meta["comparison_note"] = WEEKLY_COMPARISON_UNAVAILABLE_NOTE
            else:
                meta["weekly_comparison_available"] = True
            return completed, meta

        label = _INCOMPLETE_LABELS.get(granularity, granularity)
        note = (
            f"Pågående {label} (från {period_start}) är ofullständig och har exkluderats från trendanalys. "
            "Jämför inte den ofullständiga perioden mot fullständiga tidigare perioder och "
            "dra inga slutsatser om nedgång enbart utifrån den."
        )
        return completed, {
            **meta,
            "excluded_incomplete_period": True,
            "incomplete_period_start": period_start,
            "analysis_note": note,
        }

    if not completed and working:
        last_period = str(working[-1].get("period", ""))
        if last_period >= period_start:
            label = _INCOMPLETE_LABELS.get(granularity, granularity)
            note = (
                f"Endast pågående {label} finns i serien — ingen fullständig jämförelseperiod "
                "är tillgänglig ännu. Beskriv inte trend eller nedgång."
            )
            return working, {
                **meta,
                "excluded_incomplete_period": False,
                "incomplete_period_start": period_start,
                "internal_analysis_note": note,
            }

    result_series = completed if completed else working
    if granularity == "week" and result_series:
        last_week = str(result_series[-1].get("period", ""))[:10]
        meta["completed_week_label"] = completed_week_label(last_week)
        aligned = series_date_range(result_series, granularity)
        if aligned:
            meta["analysed_range_label"] = analysed_weekly_range_label(
                aligned["start"], aligned["end"],
            )
        if len(result_series) < 2:
            meta["weekly_comparison_available"] = False
            meta["comparison_note"] = WEEKLY_COMPARISON_UNAVAILABLE_NOTE
        else:
            meta["weekly_comparison_available"] = True

    return result_series, meta


def apply_sales_over_time_period_policy(result: dict) -> dict:
    """Return a copy of an MCP sales-over-time result with incomplete buckets handled."""
    if not isinstance(result, dict):
        return result
    if result.get("_period_policy_applied"):
        return result

    series = result.get("series") or []
    granularity = result.get("granularity", "month")
    query_dr = dict(result.get("query_date_range") or {})
    query_start = query_dr.get("requested_start") or query_dr.get("start") or (result.get("date_range") or {}).get("start")
    # Anchor incomplete-bucket detection to real today — not query end (a completed
    # Sunday would otherwise be misread as the start of an in-progress week).
    incomplete_reference = datetime.now(tz=timezone.utc).date()

    completed, meta = filter_incomplete_series(
        series, granularity, reference=incomplete_reference, query_start=query_start,
    )

    out = dict(result)
    out["series"] = completed
    aligned = series_date_range(completed, granularity)
    if aligned:
        out["date_range"] = aligned
    if query_dr:
        out["query_date_range"] = query_dr

    if meta:
        out["period_analysis"] = meta
        if meta.get("completed_week_label"):
            out["completed_week_label"] = meta["completed_week_label"]
        if meta.get("analysed_range_label"):
            out["analysed_range_label"] = meta["analysed_range_label"]
        if meta.get("comparison_note"):
            out["comparison_note"] = meta["comparison_note"]
        if meta.get("weekly_comparison_available") is not None:
            out["weekly_comparison_available"] = meta["weekly_comparison_available"]
        internal_note = meta.get("internal_analysis_note")
        analysis_note = meta.get("analysis_note")
        if analysis_note:
            out["analysis_note"] = analysis_note
        if internal_note:
            out["internal_analysis_note"] = internal_note
        # Surface user-visible limitations only for non-weekly trend gaps; weekly
        # completed-week summaries carry comparison_note in synthesis instead.
        note_for_limitations = analysis_note if granularity != "week" else None
        if note_for_limitations:
            limitations = list(result.get("limitations") or [])
            if note_for_limitations not in limitations:
                limitations.append(note_for_limitations)
            out["limitations"] = limitations
    out["_period_policy_applied"] = True
    return out
