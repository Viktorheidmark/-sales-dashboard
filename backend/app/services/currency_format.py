"""
Compact Swedish currency formatting for Analysis Assistant output.

All monetary MCP values are in whole SEK unless noted otherwise.
"""

from __future__ import annotations

import re
from typing import Any

_MONETARY_KEY_HINTS = ("revenue", "amount", "change")
_MONETARY_SKIP_HINTS = ("pct", "percent", "share", "count", "units", "orders", "rank")

_MKR_LABEL_RE = re.compile(
    r"(\d{1,3}(?:\s\d{3})*(?:,\d)?|\d+,\d)\s*mkr",
    re.IGNORECASE,
)


def _format_decimal_sv(value: float, *, one_decimal: bool = True) -> str:
    if one_decimal and abs(value - round(value)) >= 0.05:
        return f"{value:.1f}".replace(".", ",")
    return f"{int(round(value)):,}".replace(",", " ").replace("\xa0", " ")


def format_compact_sek(value: float | int | None) -> str:
    """Format SEK amounts for assistant copy: kr / tkr / mkr."""
    if value is None:
        return "—"
    amount = float(value)
    sign = "-" if amount < 0 else ""
    abs_amount = abs(amount)

    if abs_amount < 1_000:
        return f"{sign}{int(round(abs_amount))} kr"

    if abs_amount < 1_000_000:
        tkr = abs_amount / 1_000
        return f"{sign}{_format_decimal_sv(tkr)} tkr"

    mkr = abs_amount / 1_000_000
    return f"{sign}{_format_decimal_sv(mkr)} mkr"


def _parse_sv_amount(token: str) -> float:
    return float(token.replace(" ", "").replace("\xa0", "").replace(",", "."))


def _is_monetary_field(key: str) -> bool:
    lower = key.lower()
    if any(skip in lower for skip in _MONETARY_SKIP_HINTS):
        return False
    return any(hint in lower for hint in _MONETARY_KEY_HINTS)


def collect_monetary_values(payload: Any, out: list[float] | None = None) -> list[float]:
    values = out if out is not None else []
    if isinstance(payload, dict):
        for key, val in payload.items():
            if isinstance(val, (int, float)) and _is_monetary_field(key):
                values.append(float(val))
            else:
                collect_monetary_values(val, values)
    elif isinstance(payload, list):
        for item in payload:
            collect_monetary_values(item, values)
    return values


def build_currency_reference_block(raw_tool_results: list[tuple[str, dict]]) -> str:
    lines: list[str] = []
    seen: set[float] = set()

    for tool_name, result in raw_tool_results:
        for value in collect_monetary_values(result):
            if value in seen:
                continue
            seen.add(value)
            lines.append(f"- {int(value) if value == int(value) else value} SEK → {format_compact_sek(value)}")

    if not lines:
        return ""

    return (
        "\n\nVALUTAREFERENS (använd exakt dessa enheter i löptext — värden är i SEK):\n"
        + "\n".join(lines[:24])
    )


def currency_format_rules_block() -> str:
    return """
VALUTAFORMAT (obligatoriskt — råvärden är i SEK):
- Under 1 000 SEK: heltal kr (971 kr)
- 1 000 – 999 999 SEK: tkr (75,6 tkr) — ALDRIG mkr för dessa belopp
- Från 1 000 000 SEK: mkr (1,2 mkr)
- Använd formaterade belopp från VALUTAREFERENS när den finns.
"""


def _mistaken_mkr_for_tkr_value(sek_value: float) -> str | None:
    if not (1_000 <= sek_value < 1_000_000):
        return None
    mistaken = format_compact_sek(sek_value / 1_000)
    if mistaken.endswith(" tkr"):
        return mistaken.replace(" tkr", " mkr")
    return None


def sanitize_answer_currency(answer: str, raw_tool_results: list[tuple[str, dict]]) -> str:
    """Fix common LLM mistake: tkr-scale values labeled as mkr."""
    if not answer:
        return answer

    out = answer
    sek_values: list[float] = []
    for _, result in raw_tool_results:
        collect_monetary_values(result, sek_values)

    for value in sek_values:
        correct = format_compact_sek(value)
        mistaken = _mistaken_mkr_for_tkr_value(value)
        if mistaken and mistaken in out and mistaken != correct:
            out = out.replace(mistaken, correct)

    def _replace_invalid_mkr(match: re.Match[str]) -> str:
        label = match.group(0)
        mkr_amount = _parse_sv_amount(match.group(1))
        for value in sek_values:
            if 1_000 <= value < 1_000_000:
                tkr_amount = value / 1_000
                if abs(tkr_amount - mkr_amount) <= max(0.15, tkr_amount * 0.02):
                    return format_compact_sek(value)
        if mkr_amount < 1_000:
            for value in sek_values:
                if 1_000 <= value < 1_000_000 and abs(value / 1_000 - mkr_amount) <= max(
                    0.15, mkr_amount * 0.02
                ):
                    return format_compact_sek(value)
        return label

    return _MKR_LABEL_RE.sub(_replace_invalid_mkr, out)
