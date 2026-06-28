"""
Response generation — produces concise, factual Swedish business copy strictly
from the verified canonical result.

For the comparison capability the responder is deterministic: it states exact
ranges and exact figures, so it can never drift to "senaste N dagar" when the
user chose custom dates. An optional LLM polish step can be layered later, but it
must be constrained to the same verified result.
"""

from __future__ import annotations

from app.analytics.schemas import AnalysisResult
from app.services.currency_format import format_compact_sek
from app.services.period_utils import format_date_range_sv


def _range_phrase(period) -> str:
    return format_date_range_sv(period.start.isoformat(), period.end.isoformat())


def render_answer(result: AnalysisResult) -> str:
    plan = result.resolved_plan
    if plan.intent == "period_comparison":
        return _render_comparison(result)
    raise ValueError(f"Responder does not (yet) support intent '{plan.intent}'.")


def _render_comparison(result: AnalysisResult) -> str:
    spec = result.resolved_plan.comparison
    assert spec is not None
    cur = result.kpis.get("current", {})
    pri = result.kpis.get("prior", {})
    delta = result.kpis.get("delta", {})

    period_b = spec.period_b  # analyzed / current
    period_a = spec.period_a  # baseline

    b_phrase = _range_phrase(period_b)
    a_phrase = _range_phrase(period_a)
    b_rev = format_compact_sek(cur.get("revenue"))
    a_rev = format_compact_sek(pri.get("revenue"))

    lines: list[str] = []
    lines.append(
        f"Omsättningen för {b_phrase} var {b_rev}, "
        f"jämfört med {a_rev} under {a_phrase}."
    )

    pct = delta.get("revenue_pct")
    abs_change = delta.get("revenue_abs")
    if pct is not None:
        direction = "ökning" if pct >= 0 else "minskning"
        sign = "+" if pct >= 0 else ""
        lines.append(
            f"Det motsvarar en {direction} på {sign}{pct} % "
            f"({format_compact_sek(abs_change)})."
        )
    elif result.warnings:
        lines.append(result.warnings[0])

    cur_ord = cur.get("orders")
    pri_ord = pri.get("orders")
    if cur_ord is not None and pri_ord is not None:
        lines.append(
            f"Antal ordrar: {int(cur_ord)} mot {int(pri_ord)} under jämförelseperioden."
        )

    return " ".join(lines)
