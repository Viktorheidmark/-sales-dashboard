"""
Shared tenant chart branding for server-side renderers (PDF export, etc.).

Mirrors frontend/src/theme/tenantBranding.ts — keep chart_primary values in sync.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Neutral baseline for period-comparison bars (matches in-app comparisonMuted).
COMPARISON_BASELINE_COLOR = "#94A3B8"

# Semantic colors — independent of tenant brand.
NEGATIVE_CHANGE_COLOR = "#ef4444"
POSITIVE_CHANGE_COLOR = "#16a34a"


@dataclass(frozen=True)
class TenantChartTheme:
    chart_primary: str
    chart_muted: str


_SOLVIGO_DEFAULT = TenantChartTheme(chart_primary="#3B82F6", chart_muted="#93C5FD")

# Solvigo fallback accent when supplier is unknown (matches chart default).
SOLVIGO_ACCENT_COLOR = _SOLVIGO_DEFAULT.chart_primary

_TENANT_RULES: list[tuple[str, TenantChartTheme]] = [
    (
        r"coca.?cola",
        TenantChartTheme(chart_primary="#C62828", chart_muted="#F2B8B5"),
    ),
    (
        r"pepsi",
        TenantChartTheme(chart_primary="#1463D8", chart_muted="#A9C8FF"),
    ),
    (
        r"orkla",
        TenantChartTheme(chart_primary="#E56A25", chart_muted="#F6C3A5"),
    ),
    (
        r"estrella",
        TenantChartTheme(chart_primary="#6C3CCB", chart_muted="#D1B8F6"),
    ),
]


def tenant_chart_theme_for_supplier(supplier_name: str) -> TenantChartTheme:
    """Resolve tenant chart colors from supplier display name."""
    import re

    name = (supplier_name or "").strip()
    if not name:
        return _SOLVIGO_DEFAULT
    for pattern, theme in _TENANT_RULES:
        if re.search(pattern, name, re.IGNORECASE):
            return theme
    return _SOLVIGO_DEFAULT


def pdf_header_accent_color(supplier_name: str) -> str:
    """Tenant primary accent for PDF header wordmark (symbol + Sales Intelligence)."""
    return tenant_chart_theme_for_supplier(supplier_name).chart_primary


def theme_from_payload_or_supplier(
    chart_payload: Optional[dict],
    supplier_name: str,
) -> TenantChartTheme:
    """Prefer explicit chart payload theme hints; fall back to supplier name lookup."""
    if chart_payload:
        embedded = chart_payload.get("tenant_theme") or {}
        if isinstance(embedded, dict):
            primary = embedded.get("chart_primary") or embedded.get("primary_color")
            muted = embedded.get("chart_muted") or embedded.get("muted_color")
            if primary:
                return TenantChartTheme(
                    chart_primary=str(primary),
                    chart_muted=str(muted or _SOLVIGO_DEFAULT.chart_muted),
                )
    return tenant_chart_theme_for_supplier(supplier_name)


def is_period_comparison_chart(chart_payload: dict) -> bool:
    variant = str(chart_payload.get("chart_variant") or "")
    return variant in ("period_comparison", "decline_comparison")


def resolve_bar_fill_colors(
    chart_payload: dict,
    y_vals: list[float],
    *,
    supplier_name: str = "",
) -> list[str]:
    """
    Bar fill colors for PDF matplotlib rendering.

    Period comparison: baseline gray, analyzed period tenant primary (even when negative).
    Other bar charts: tenant primary, with semantic red for negative values.
    """
    theme = theme_from_payload_or_supplier(chart_payload, supplier_name)
    n = len(y_vals)

    if is_period_comparison_chart(chart_payload) and n >= 1:
        colors = [COMPARISON_BASELINE_COLOR] * n
        emphasis = int(chart_payload.get("emphasis_index", 1))
        if 0 <= emphasis < n:
            colors[emphasis] = theme.chart_primary
        else:
            # Baseline first, analyzed second — same order as in-app chart.
            if n >= 2:
                colors[1] = theme.chart_primary
            else:
                colors[0] = theme.chart_primary
        return colors

    return [
        NEGATIVE_CHANGE_COLOR if v < 0 else theme.chart_primary
        for v in y_vals
    ]


def change_text_color(value: float) -> str:
    """Semantic KPI delta text color (not tenant brand)."""
    if value < 0:
        return NEGATIVE_CHANGE_COLOR
    if value > 0:
        return POSITIVE_CHANGE_COLOR
    return "#334155"
