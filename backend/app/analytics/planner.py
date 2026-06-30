"""
Planning agent — explicit period comparison capability (Phase 2 vertical slice).

For the comparison capability the planner is intentionally **deterministic**:
parsing exact dates from free text or a composer action is safer and more
correct than letting a model invent periods (planner rule #1: never invent
periods). An LLM semantic layer is added for other intents in later phases; for
comparison, deterministic parsing is authoritative.

The planner produces a canonical ``AnalysisPlan``:
* a fully-resolved ``period_comparison`` plan when two exact periods are present
  (free text or composer), or
* a ``clarification`` plan (``clarification_type="comparison_dates"``) that opens
  the in-chat composer when comparison intent is detected but two periods are
  not resolvable.

It returns ``None`` when the message is not a comparison request, signalling the
orchestrator to defer to the legacy pipeline.
"""

from __future__ import annotations

import calendar
import re
from datetime import date
from typing import Optional

from app.analytics.schemas import (
    AnalysisPlan,
    ComparisonSource,
    ComparisonSpec,
    ComparisonType,
    DateRange,
)
from app.services.period_utils import (
    _MONTHS_SV,
    _MONTHS_SV_SHORT,
    default_data_bounds,
    latest_completed_date,
)

# Comparison intent / vagueness detection lives in comparison_labels; reuse it so
# the new planner and the legacy guard agree on what "a comparison" is.
from app.services.comparison_labels import (
    classify_comparison_dimension,
    has_ambiguous_comparison_intent,
    question_requests_comparison,
)

# KPI-totals comparison (revenue/orders/units/AOV) for two exact periods. Per
# product/region drivers for arbitrary custom ranges are a later executor
# enhancement (a dedicated compare_periods query); they are not included here, so
# the plan does not promise driver sections it cannot ground.
_COMPARISON_OUTPUT_SECTIONS = ["summary", "kpis", "comparison"]
_COMPARISON_DIMENSIONS: list = []

_MONTH_INDEX: dict[str, int] = {}
for _i, _name in enumerate(_MONTHS_SV, start=1):
    _MONTH_INDEX[_name] = _i
for _i, _name in enumerate(_MONTHS_SV_SHORT, start=1):
    _MONTH_INDEX.setdefault(_name, _i)

_MONTH_TOKEN_RE = re.compile(
    r"\b(" + "|".join(sorted(_MONTH_INDEX.keys(), key=len, reverse=True)) + r")\b"
    r"(?:\s+(\d{4}))?",
    re.IGNORECASE,
)

_ISO_RANGE_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2})\s*(?:till|–|-|to|until)\s*(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)

_DAY_MONTH_RANGE_RE = re.compile(
    r"(\d{1,2})\s*[–\-]\s*(\d{1,2})\s+("
    + "|".join(sorted(_MONTH_INDEX.keys(), key=len, reverse=True))
    + r")(?:\s+(\d{4}))?",
    re.IGNORECASE,
)

_ROLLING_PAIR_RE = re.compile(
    r"senaste\s+(\d{1,3})\s*(?:dagar|dagarna|dag)\b.*?"
    r"(?:mot|jämf\w*|föregående|tidigare).*?(?:(\d{1,3})\s*(?:dagar|dagarna|dag)\b)?",
    re.IGNORECASE | re.DOTALL,
)

_YTD_TOKEN_RE = re.compile(r"\b(i\s+år|hittills\s+i\s+år|detta\s+år|årets)\b", re.IGNORECASE)
_PREV_YEAR_TOKEN_RE = re.compile(
    r"(förra\s+år\w*|föregående\s+år\w*|samma\s+period\s+(?:förra|föregående)\s+år\w*|i\s+fjol)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Period building helpers
# ---------------------------------------------------------------------------


def _reference_year() -> int:
    return latest_completed_date().year


def _month_range(month: int, year: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _extract_month_periods(message: str) -> list[DateRange]:
    """Find month tokens (with optional year) and turn them into full-month ranges."""
    matches = list(_MONTH_TOKEN_RE.finditer(message))
    if not matches:
        return []

    raw: list[tuple[int, Optional[int]]] = []
    for m in matches:
        idx = _MONTH_INDEX[m.group(1).lower()]
        year = int(m.group(2)) if m.group(2) else None
        raw.append((idx, year))

    # If only one token carries a year, apply it to every token (e.g. "mars och april 2026").
    explicit_years = {y for _, y in raw if y is not None}
    fallback_year = next(iter(explicit_years)) if len(explicit_years) == 1 else _reference_year()

    periods: list[DateRange] = []
    for idx, year in raw:
        y = year if year is not None else fallback_year
        start, end = _month_range(idx, y)
        periods.append(DateRange(start=start, end=end, label=f"{_MONTHS_SV[idx - 1]} {y}"))
    return periods


def _extract_day_month_ranges(message: str) -> list[DateRange]:
    """Parse intra-month day spans such as ``1–8 mars`` (requires two distinct ranges)."""
    matches = list(_DAY_MONTH_RANGE_RE.finditer(message))
    if len(matches) < 2:
        return []

    explicit_years = [int(m.group(4)) for m in matches if m.group(4)]
    fallback_year = explicit_years[0] if len(explicit_years) == 1 else _reference_year()

    periods: list[DateRange] = []
    seen: set[tuple[date, date]] = set()
    for m in matches:
        month = _MONTH_INDEX[m.group(3).lower()]
        year = int(m.group(4)) if m.group(4) else fallback_year
        start_day = int(m.group(1))
        end_day = int(m.group(2))
        if end_day < start_day:
            continue
        last_day = calendar.monthrange(year, month)[1]
        if start_day < 1 or end_day > last_day:
            continue
        start = date(year, month, start_day)
        end = date(year, month, end_day)
        key = (start, end)
        if key in seen:
            continue
        seen.add(key)
        label = f"{start_day}–{end_day} {_MONTHS_SV[month - 1]} {year}"
        periods.append(DateRange(start=start, end=end, label=label))
    return periods


def _extract_iso_ranges(message: str) -> list[DateRange]:
    ranges: list[DateRange] = []
    for m in _ISO_RANGE_RE.finditer(message):
        try:
            start = date.fromisoformat(m.group(1))
            end = date.fromisoformat(m.group(2))
        except ValueError:
            continue
        if end >= start:
            ranges.append(DateRange(start=start, end=end))
    return ranges


def _order_baseline_current(p1: DateRange, p2: DateRange) -> tuple[DateRange, DateRange]:
    """period_a is always the earlier baseline; period_b the later analyzed window."""
    return (p1, p2) if p1.start <= p2.start else (p2, p1)


def _rolling_pair(message: str) -> Optional[tuple[DateRange, DateRange]]:
    m = _ROLLING_PAIR_RE.search(message)
    if not m:
        return None
    n = int(m.group(1))
    n2 = int(m.group(2)) if m.group(2) else n
    if n2 != n:
        # Asymmetric rolling windows are ambiguous — defer to composer.
        return None
    end_b = latest_completed_date()
    from datetime import timedelta

    start_b = end_b - timedelta(days=n - 1)
    end_a = start_b - timedelta(days=1)
    start_a = end_a - timedelta(days=n - 1)
    period_a = DateRange(start=start_a, end=end_a, label=f"föregående {n} dagar")
    period_b = DateRange(start=start_b, end=end_b, label=f"senaste {n} dagarna")
    return period_a, period_b


def _ytd_vs_prior_year(message: str) -> Optional[tuple[DateRange, DateRange]]:
    if not (_YTD_TOKEN_RE.search(message) and _PREV_YEAR_TOKEN_RE.search(message)):
        return None
    end_b = latest_completed_date()
    start_b = date(end_b.year, 1, 1)
    start_a = date(end_b.year - 1, 1, 1)
    end_a = date(end_b.year - 1, end_b.month, end_b.day)
    # Exact equivalent YTD windows — no vague "helåret"/"hittills" labels. UI-facing
    # copy is formatted via readable_range → format_date_range_sv (e.g. 1 jan–27 jun 2026).
    period_a = DateRange(start=start_a, end=end_a)
    period_b = DateRange(start=start_b, end=end_b)
    return period_a, period_b


# ---------------------------------------------------------------------------
# Free-text comparison parsing
# ---------------------------------------------------------------------------


def parse_explicit_comparison(message: str) -> Optional[ComparisonSpec]:
    """Parse a free-text message into an exact two-period ComparisonSpec, or None."""
    msg = (message or "").strip()
    if not msg:
        return None

    rolling = _rolling_pair(msg)
    if rolling:
        a, b = rolling
        return ComparisonSpec(
            period_a=a, period_b=b, comparison_type="rolling", source="explicit_free_text"
        )

    yoy = _ytd_vs_prior_year(msg)
    if yoy:
        a, b = yoy
        return ComparisonSpec(
            period_a=a, period_b=b, comparison_type="year_over_year", source="explicit_free_text"
        )

    iso_ranges = _extract_iso_ranges(msg)
    if len(iso_ranges) >= 2:
        a, b = _order_baseline_current(iso_ranges[0], iso_ranges[1])
        return ComparisonSpec(
            period_a=a, period_b=b, comparison_type="custom", source="explicit_free_text"
        )

    day_month_ranges = _extract_day_month_ranges(msg)
    if len(day_month_ranges) >= 2:
        a, b = _order_baseline_current(day_month_ranges[0], day_month_ranges[1])
        return ComparisonSpec(
            period_a=a, period_b=b, comparison_type="custom", source="explicit_free_text"
        )

    months = _extract_month_periods(msg)
    if len(months) == 2:
        a, b = _order_baseline_current(months[0], months[1])
        return ComparisonSpec(
            period_a=a, period_b=b, comparison_type="month_over_month", source="explicit_free_text"
        )

    return None


def comparison_spec_from_composer(context: dict) -> Optional[ComparisonSpec]:
    """Build an exact ComparisonSpec from a composer ``compare_periods`` action."""
    try:
        a_start = date.fromisoformat(str(context["period_a_start"])[:10])
        a_end = date.fromisoformat(str(context["period_a_end"])[:10])
        b_start = date.fromisoformat(str(context["period_b_start"])[:10])
        b_end = date.fromisoformat(str(context["period_b_end"])[:10])
    except (KeyError, ValueError, TypeError):
        return None
    if a_end < a_start or b_end < b_start:
        return None
    mode = str(context.get("comparison_mode") or "custom")
    source: ComparisonSource = "preset" if mode == "preset" else "comparison_composer"
    comparison_type: ComparisonType = "custom"
    period_a = DateRange(start=a_start, end=a_end)
    period_b = DateRange(start=b_start, end=b_end)
    return ComparisonSpec(
        period_a=period_a, period_b=period_b, comparison_type=comparison_type, source=source
    )


# ---------------------------------------------------------------------------
# Plan construction
# ---------------------------------------------------------------------------


def _comparison_plan(spec: ComparisonSpec, reasoning: str) -> AnalysisPlan:
    return AnalysisPlan(
        intent="period_comparison",
        metric="revenue",
        dimensions=list(_COMPARISON_DIMENSIONS),
        primary_period=spec.period_b,
        comparison=spec,
        chart_intent="comparison_bar",
        output_sections=list(_COMPARISON_OUTPUT_SECTIONS),
        needs_clarification=False,
        confidence=0.95,
        reasoning_summary=reasoning,
    )


def _dimension_clarification_plan(reasoning: str) -> AnalysisPlan:
    return AnalysisPlan(
        intent="clarification",
        metric="revenue",
        chart_intent="none",
        output_sections=[],
        needs_clarification=True,
        clarification_type="comparison_dimension",
        confidence=0.5,
        reasoning_summary=reasoning,
    )


def _clarification_plan(reasoning: str) -> AnalysisPlan:
    return AnalysisPlan(
        intent="clarification",
        metric="revenue",
        chart_intent="none",
        output_sections=[],
        needs_clarification=True,
        clarification_type="comparison_dates",
        confidence=0.5,
        reasoning_summary=reasoning,
    )


def plan_comparison(
    message: str,
    follow_up_action: Optional[dict] = None,
) -> Optional[AnalysisPlan]:
    """
    Produce a canonical comparison plan.

    Returns:
        * a ``period_comparison`` plan when two exact periods resolve,
        * a ``clarification`` plan when comparison intent is present but vague,
        * ``None`` when this is not a comparison request (defer to legacy).
    """
    # 1. Structured composer action is the highest-trust source of exact dates.
    if follow_up_action and str(follow_up_action.get("action") or "") == "compare_periods":
        spec = comparison_spec_from_composer(follow_up_action.get("context") or {})
        if spec is not None:
            return _comparison_plan(spec, "Composer supplied two exact periods.")
        return _clarification_plan("Composer action missing valid period dates.")

    msg = (message or "").strip()

    # 2. Explicit free-text comparison with two resolvable periods.
    spec = parse_explicit_comparison(msg)
    if spec is not None:
        return _comparison_plan(
            spec, f"Parsed explicit {spec.comparison_type} comparison from free text."
        )

    dimension = classify_comparison_dimension(msg)
    if dimension in ("product", "region"):
        return None
    if dimension == "ambiguous":
        return _dimension_clarification_plan(
            "Comparison intent without a clear product, region, or period dimension."
        )
    if dimension == "period":
        return _clarification_plan("Period comparison without two resolvable periods.")

    # Legacy fallback for period cues not captured by classify_comparison_dimension.
    if question_requests_comparison(msg) or has_ambiguous_comparison_intent(msg):
        return _clarification_plan("Comparison intent without two resolvable periods.")

    # 4. Not a comparison request.
    return None
