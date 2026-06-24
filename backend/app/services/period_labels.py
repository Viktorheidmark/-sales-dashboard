"""
Centralized human-readable Swedish period labels for answers and charts.

Derived from verified date ranges, period kind metadata, and user phrasing.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from app.services.period_utils import (
    _FULL_PERIOD_RE,
    _LAST_YEAR_RE,
    default_data_bounds,
    default_decline_comparison_days,
    format_date_range_sv,
    is_current_year_phrase,
    resolve_period_range,
)


def _parse(d: str | None) -> date | None:
    if not d:
        return None
    try:
        return date.fromisoformat(str(d)[:10])
    except ValueError:
        return None


def _span_days(date_range: dict | None) -> int:
    if not date_range or not date_range.get("start") or not date_range.get("end"):
        return 0
    s, e = _parse(date_range["start"]), _parse(date_range["end"])
    if not s or not e:
        return 0
    return (e - s).days + 1


def _is_ytd_range(date_range: dict | None) -> bool:
    if not date_range:
        return False
    s, e = _parse(date_range.get("start")), _parse(date_range.get("end"))
    return bool(s and e and s.month == 1 and s.day == 1 and s.year == e.year)


def message_specifies_period(message: str) -> bool:
    """True when the user named a period in the question."""
    return bool(resolve_period_range(message or ""))


def _kind_from_resolved(message: str, resolved: dict) -> str:
    if resolved.get("period_kind"):
        return str(resolved["period_kind"])
    if is_current_year_phrase(message):
        return "year_to_date"
    if _FULL_PERIOD_RE.search((message or "").lower()):
        return "full_history"
    if _LAST_YEAR_RE.search((message or "").lower()):
        return "previous_year"
    if resolved.get("completed_week"):
        return "previous_completed_week"
    days = resolved.get("days")
    if days == 30:
        return "rolling_30"
    if days == 90:
        return "rolling_90"
    if days == 180:
        return "rolling_180"
    return "phrase_resolved"


def _kind_from_date_span(date_range: dict | None) -> str:
    if _is_ytd_range(date_range):
        return "year_to_date"
    span = _span_days(date_range)
    if span == 90:
        return "ui_default"
    if span == 30:
        return "ui_default_30"
    if span == 180:
        return "ui_default_180"
    data_min, data_max = default_data_bounds()
    s, e = _parse((date_range or {}).get("start")), _parse((date_range or {}).get("end"))
    if s and e and s == data_min and e == data_max:
        return "full_history"
    if s and e and s.month == 1 and s.day == 1 and e.month == 12 and e.day == 31 and s.year == e.year:
        return "previous_year"
    return "exact_range"


def infer_period_kind(
    date_range: dict | None,
    *,
    message: str = "",
    period_kind_hint: str | None = None,
) -> str:
    if period_kind_hint:
        hint = period_kind_hint
        if hint == "current_year":
            return "year_to_date"
        return hint
    if message_specifies_period(message):
        resolved = resolve_period_range(message)
        if resolved.get("start_date") and resolved.get("end_date"):
            return _kind_from_resolved(message, resolved)
    return _kind_from_date_span(date_range)


def answer_period_phrase(
    period_kind: str,
    date_range: dict | None,
    message: str = "",
) -> str:
    """Phrase for answer body, e.g. 'de senaste 90 dagarna'."""
    s, e = (date_range or {}).get("start"), (date_range or {}).get("end")

    if period_kind in ("year_to_date", "current_year") or _is_ytd_range(date_range):
        return "hittills i år"

    if period_kind == "full_history":
        return "över hela tillgängliga perioden"

    if period_kind == "full_history_halves":
        return "över hela tillgängliga perioden (jämfört med föregående lika långa period)"

    if period_kind == "previous_year" and s:
        year = _parse(s)
        if year:
            return f"under {year.year}"

    if period_kind in ("previous_completed_week", "current_week") or (
        message_specifies_period(message)
        and resolve_period_range(message).get("completed_week")
    ):
        return "senaste avslutade veckan"

    if period_kind in ("ui_default", "safe_fallback", "rolling_90", "rolling_quarter"):
        return "de senaste 90 dagarna"

    if period_kind in ("ui_default_30", "rolling_30"):
        return "de senaste 30 dagarna"

    if period_kind == "ui_default_180" or period_kind == "rolling_180":
        return "de senaste 180 dagarna"

    if period_kind.startswith("rolling_"):
        try:
            days = int(period_kind.split("_", 1)[1])
            return f"de senaste {days} dagarna"
        except ValueError:
            pass

    if s and e:
        return format_date_range_sv(s, e)

    return "de senaste 90 dagarna"


def chart_period_suffix(
    period_kind: str,
    date_range: dict | None,
    message: str = "",
) -> str:
    """Compact suffix for chart subtitles, e.g. 'senaste 90 dagarna'."""
    phrase = answer_period_phrase(period_kind, date_range, message)
    if phrase == "hittills i år":
        return "hittills i år"
    if phrase == "över hela tillgängliga perioden":
        return "hela tillgängliga perioden"
    if phrase == "över hela tillgängliga perioden (jämfört med föregående lika långa period)":
        return "hela tillgängliga perioden (mot föregående halva)"
    if phrase == "senaste avslutade veckan":
        return "senaste avslutade veckan"
    if phrase.startswith("under "):
        return phrase
    if phrase.startswith("de senaste "):
        return phrase[3:]  # drop leading "de "
    return phrase


def answer_period_opening(
    period_kind: str,
    date_range: dict | None,
    message: str = "",
) -> str:
    """Full opening fragment, e.g. 'Under de senaste 90 dagarna'."""
    phrase = answer_period_phrase(period_kind, date_range, message)
    if phrase.startswith("under "):
        return f"Under {phrase}"
    return f"Under {phrase}"


def _date_range_from_result(result: dict, tool_name: str = "") -> dict:
    if result.get("date_range"):
        return result["date_range"]
    if tool_name == "get_declining_products":
        return result.get("latest_period") or {}
    if tool_name == "get_revenue_drivers":
        return result.get("current_period") or {}
    return {}


def apply_period_labels(
    result: dict,
    question: str = "",
    plan_args: dict | None = None,
    *,
    tool_name: str = "",
) -> dict:
    """Attach period_label_answer and period_label_chart to a tool result."""
    if not isinstance(result, dict):
        return result
    plan_args = plan_args or {}
    date_range = _date_range_from_result(result, tool_name)
    kind = infer_period_kind(
        date_range,
        message=question,
        period_kind_hint=plan_args.get("_period_kind") or result.get("_period_kind"),
    )
    if tool_name == "get_declining_products" and not date_range:
        days = int(result.get("comparison_days") or 30)
        hinted = plan_args.get("_period_kind") or result.get("_period_kind")
        if hinted:
            kind = str(hinted)
        elif not message_specifies_period(question) and days >= default_decline_comparison_days():
            kind = "full_history_halves"
        else:
            kind = "rolling_30" if days == 30 else f"rolling_{days}"

    result["_period_kind"] = kind
    result["period_label_answer"] = answer_period_phrase(kind, date_range, question)
    result["period_label_chart"] = chart_period_suffix(kind, date_range, question)
    result["period_label_opening"] = answer_period_opening(kind, date_range, question)
    return result


def append_chart_period(base: str, result: dict) -> str:
    """Append chart period suffix to a subtitle when available."""
    suffix = result.get("period_label_chart")
    if not suffix:
        return base
    if suffix in base:
        return base
    return f"{base} · {suffix}"
