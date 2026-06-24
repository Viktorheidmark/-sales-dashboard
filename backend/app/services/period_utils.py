"""
Shared incomplete-period handling for sales-over-time series.

Mirrors the dashboard SalesTrend chart policy: exclude the current
incomplete day/week/month bucket from trend analysis when a completed
history exists.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional

_INCOMPLETE_LABELS = {"day": "dag", "week": "vecka", "month": "månad"}

WEEKLY_COMPARISON_UNAVAILABLE_NOTE = (
    "Det finns inte tillräckligt med jämförbar veckodata i den valda perioden "
    "för att bedöma utvecklingen mot föregående vecka."
)

DEFAULT_DATASET_LOOKBACK_DAYS = 730  # matches seed_demo_data.HISTORY_DAYS

_CURRENT_YEAR_RE = re.compile(
    r"("
    r"detta\s+år|"
    r"hittills\s+i\s+år|"
    r"under\s+hela\s+år[ae]t|"
    r"hela\s+år[ae]t|"
    r"under\s+året|"
    r"från\s+början\s+av\s+året|"
    r"årets\s+försäljning|"
    r"försäljningen\s+överlag\s+i\s+år|"
    r"hur\s+går\s+det\s+i\s+år|"
    r"hur\s+ser\s+försäljningen\s+ut\s+i\s+år|"
    r"hur\s+har\s+försäljningen\s+utvecklats\s+i\s+år|"
    r"hur\s+ser\s+försäljningen\s+överlag\s+ut\s+detta\s+år|"
    r"\bi\s+år\b"
    r")",
    re.IGNORECASE,
)
_LAST_YEAR_RE = re.compile(r"förra\s+år[ae]t|föregående\s+år[ae]t|förra\s+kalenderåret", re.IGNORECASE)
_FULL_PERIOD_RE = re.compile(r"(?:över\s+)?hela\s+period[ae]n|all\s+tillgänglig\s+(?:data|tid)|all\s+tid\b", re.IGNORECASE)
_ROLLING_YEAR_RE = re.compile(r"senaste\s+året", re.IGNORECASE)

_MONTHS_SV = (
    "januari", "februari", "mars", "april", "maj", "juni",
    "juli", "augusti", "september", "oktober", "november", "december",
)
_MONTHS_SV_SHORT = (
    "jan", "feb", "mar", "apr", "maj", "jun",
    "jul", "aug", "sep", "okt", "nov", "dec",
)


def completed_week_bounds(reference: Optional[date] = None) -> tuple[date, date]:
    """Monday–Sunday of the most recent fully completed ISO week."""
    today = reference or datetime.now(tz=timezone.utc).date()
    current_monday = today - timedelta(days=today.weekday())
    last_sunday = current_monday - timedelta(days=1)
    last_monday = last_sunday - timedelta(days=6)
    return last_monday, last_sunday


def latest_completed_date(reference: Optional[date] = None) -> date:
    """Latest day with complete transactional data (demo seed ends yesterday)."""
    ref = reference or datetime.now(tz=timezone.utc).date()
    return ref - timedelta(days=1)


def default_data_bounds(reference: Optional[date] = None) -> tuple[date, date]:
    end = latest_completed_date(reference)
    start = end - timedelta(days=DEFAULT_DATASET_LOOKBACK_DAYS - 1)
    return start, end


def clamp_date_range(start: date, end: date, data_min: date, data_max: date) -> tuple[date, date]:
    start = max(start, data_min)
    end = min(end, data_max)
    if start > end:
        start = end
    return start, end


def is_current_year_phrase(message: str) -> bool:
    """True when the message refers to the current calendar year to date."""
    return bool(_CURRENT_YEAR_RE.search((message or "").lower()))


def current_year_period_range(
    reference: Optional[date] = None,
    data_min: Optional[date] = None,
    data_max: Optional[date] = None,
) -> dict:
    """January 1 of reference year through latest completed available date."""
    today = reference or datetime.now(tz=timezone.utc).date()
    if data_min is None or data_max is None:
        default_min, default_max = default_data_bounds(today)
        data_min = data_min or default_min
        data_max = data_max or default_max
    completed_end = min(latest_completed_date(today), data_max)
    start, end = clamp_date_range(date(today.year, 1, 1), completed_end, data_min, data_max)
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "days": (end - start).days + 1,
        "period_kind": "current_year",
    }


def resolve_period_range(
    message: str,
    reference: Optional[date] = None,
    data_min: Optional[date] = None,
    data_max: Optional[date] = None,
) -> dict:
    """Derive start_date/end_date from relative Swedish period phrases."""
    today = reference or datetime.now(tz=timezone.utc).date()
    if data_min is None or data_max is None:
        default_min, default_max = default_data_bounds(today)
        data_min = data_min or default_min
        data_max = data_max or default_max

    completed_end = min(latest_completed_date(today), data_max)
    msg = message.lower()

    if _FULL_PERIOD_RE.search(msg):
        start, end = clamp_date_range(data_min, data_max, data_min, data_max)
        return {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "days": (end - start).days + 1,
            "period_kind": "full_history",
        }

    if _LAST_YEAR_RE.search(msg):
        year = today.year - 1
        start, end = clamp_date_range(date(year, 1, 1), date(year, 12, 31), data_min, data_max)
        return {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "days": (end - start).days + 1,
            "period_kind": "previous_year",
        }

    if is_current_year_phrase(msg):
        return current_year_period_range(today, data_min, data_max)

    if _ROLLING_YEAR_RE.search(msg):
        end = completed_end
        start, end = clamp_date_range(end - timedelta(days=364), end, data_min, data_max)
        return {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "days": (end - start).days + 1,
        }

    match = re.search(r"senaste\s+(\d+)\s+dag", msg)
    if match:
        days = int(match.group(1))
        end = completed_end
        start, end = clamp_date_range(end - timedelta(days=days - 1), end, data_min, data_max)
        return {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "days": days,
            "period_kind": f"rolling_{days}",
        }

    if re.search(r"senaste\s+veck", msg):
        week_start, week_end = completed_week_bounds(today)
        week_start, week_end = clamp_date_range(week_start, week_end, data_min, data_max)
        return {
            "start_date": week_start.isoformat(),
            "end_date": week_end.isoformat(),
            "days": (week_end - week_start).days + 1,
            "completed_week": True,
            "period_kind": "previous_completed_week",
        }

    if re.search(r"senaste\s+kvartalet", msg):
        end = completed_end
        start, end = clamp_date_range(end - timedelta(days=89), end, data_min, data_max)
        return {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "days": 90,
            "period_kind": "rolling_quarter",
        }

    if re.search(r"senaste\s+90", msg):
        days = 90
        end = completed_end
        start, end = clamp_date_range(end - timedelta(days=days - 1), end, data_min, data_max)
        return {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "days": days,
            "period_kind": "rolling_90",
        }

    if re.search(r"senaste\s+180", msg):
        days = 180
        end = completed_end
        start, end = clamp_date_range(end - timedelta(days=days - 1), end, data_min, data_max)
        return {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "days": days,
            "period_kind": "rolling_180",
        }

    return {}


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
    return format_compact_date_range_sv(week_monday, sunday)


def format_compact_date_range_sv(start: date | str, end: date | str) -> str:
    """Compact Swedish range for chart summaries — never truncated."""
    if isinstance(start, str):
        start = date.fromisoformat(start[:10])
    if isinstance(end, str):
        end = date.fromisoformat(end[:10])

    if start.year == end.year and start.month == end.month:
        return f"{start.day}–{end.day} {_MONTHS_SV[end.month - 1]}"
    if start.year == end.year:
        return (
            f"{start.day} {_MONTHS_SV[start.month - 1]}"
            f"–{end.day} {_MONTHS_SV[end.month - 1]}"
        )
    return (
        f"{start.day} {_MONTHS_SV_SHORT[start.month - 1]} {start.year}"
        f"–{end.day} {_MONTHS_SV_SHORT[end.month - 1]} {end.year}"
    )


def week_bucket_bounds(
    week_monday: date | str,
    query_start: Optional[date | str] = None,
) -> tuple[date, date]:
    """Actual inclusive bounds for a weekly bucket (handles partial start weeks)."""
    if isinstance(week_monday, str):
        week_monday = date.fromisoformat(week_monday[:10])
    sunday = week_monday + timedelta(days=6)
    if query_start is not None:
        if isinstance(query_start, str):
            query_start = date.fromisoformat(query_start[:10])
        if is_partial_start_week(week_monday, query_start):
            return query_start, sunday
    return week_monday, sunday


def is_complete_iso_week_bucket(
    week_monday: date | str,
    query_start: Optional[date | str] = None,
) -> bool:
    if isinstance(week_monday, str):
        week_monday = date.fromisoformat(week_monday[:10])
    if week_monday.weekday() != 0:
        return False
    if query_start is not None:
        if isinstance(query_start, str):
            query_start = date.fromisoformat(query_start[:10])
        if is_partial_start_week(week_monday, query_start):
            return False
    return True


def format_week_series_label_sv(
    week_monday: date | str,
    query_start: Optional[date | str] = None,
) -> str:
    """Human label for a weekly series point — 'veckan' only for full ISO weeks."""
    start, end = week_bucket_bounds(week_monday, query_start)
    compact = format_compact_date_range_sv(start, end)
    if isinstance(week_monday, str):
        week_monday = date.fromisoformat(week_monday[:10])
    prefix = "veckan" if is_complete_iso_week_bucket(week_monday, query_start) else "perioden"
    return f"{prefix} {compact}"


def enrich_weekly_series_labels(
    series: list[dict],
    query_start: Optional[str] = None,
) -> None:
    """Attach period_label to weekly series rows for synthesis and charts."""
    for point in series:
        period = str(point.get("period", ""))[:10]
        if not period:
            continue
        point["period_label"] = format_week_series_label_sv(period, query_start)


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

    if granularity == "week" and completed:
        enrich_weekly_series_labels(completed, query_start)

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
