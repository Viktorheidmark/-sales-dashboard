"""
Server-side PDF generation for saved insights.

Approach: reportlab (Platypus) for document layout + matplotlib (Agg backend)
for chart rendering to in-memory PNG. No browser required. Both libraries are
pure-Python installable with pip; no system-level dependencies beyond what
reportlab/matplotlib ship themselves.

Security:
- No supplier_id, JWT, database URLs, raw SQL, or internal paths in output.
- Chart values come only from the saved chart_payload dict; never from AI prose.
- Supplier name comes from the authenticated JWT claim; safe to show.
"""

import io
import textwrap
from datetime import datetime, timezone
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # must be set before pyplot import
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)
from reportlab.lib.colors import HexColor

# ---------------------------------------------------------------------------
# Brand palette (mirrors Solvigo Tailwind config)
# ---------------------------------------------------------------------------
BRAND_BLUE = HexColor("#4169e1")
SLATE_900  = HexColor("#0f172a")
SLATE_700  = HexColor("#334155")
ZINC_800   = HexColor("#27272a")
ZINC_500   = HexColor("#71717a")
ZINC_200   = HexColor("#e4e4e7")
ZINC_50    = HexColor("#fafafa")
AMBER_600  = HexColor("#d97706")
WHITE      = colors.white

CHART_COLORS = ["#4169e1", "#a5b4fc", "#c7d2fe", "#e0e7ff"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_date(iso: str) -> str:
    """Format ISO timestamp to Swedish-style short date+time."""
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%Y-%m-%d kl. %H:%M UTC")
    except Exception:
        return iso


def _tool_label(tool_name: str) -> str:
    """Convert MCP tool name to human-readable Swedish label."""
    return (
        tool_name
        .replace("get_", "")
        .replace("_", " ")
        .capitalize()
    )


def _wrap_text(text: str, width: int = 90) -> str:
    """Wrap long lines for paragraph display."""
    return "\n".join(textwrap.fill(line, width) for line in text.splitlines())


# ---------------------------------------------------------------------------
# Chart → PNG bytes via matplotlib
# ---------------------------------------------------------------------------

def _render_chart_png(chart_payload: dict, width_px: int = 900, height_px: int = 360) -> bytes:
    chart_type = chart_payload.get("chart_type", "")
    data = chart_payload.get("data") or []
    x_key = chart_payload.get("x_key", "")
    y_key = chart_payload.get("y_key", "")

    dpi = 150
    fig_w = width_px / dpi
    fig_h = height_px / dpi

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#fafafa")
    for spine in ax.spines.values():
        spine.set_color("#e4e4e7")

    x_vals = [str(row.get(x_key, "")) for row in data]
    y_vals = [float(row.get(y_key, 0) or 0) for row in data]

    if chart_type == "line_chart":
        ax.plot(x_vals, y_vals, color=CHART_COLORS[0], linewidth=2.5, zorder=3)
        ax.fill_between(range(len(x_vals)), y_vals, alpha=0.12, color=CHART_COLORS[0])
        ax.set_xticks(range(len(x_vals)))
        ax.set_xticklabels(x_vals, rotation=40, ha="right", fontsize=7.5, color="#71717a")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.tick_params(axis="y", labelsize=7.5, colors="#71717a")
        ax.tick_params(axis="x", length=0)
        ax.tick_params(axis="y", length=0)
        ax.grid(axis="y", linestyle="--", linewidth=0.5, color="#e4e4e7", zorder=0)
        ax.set_axisbelow(True)

    elif chart_type == "bar_chart":
        bar_colors = [CHART_COLORS[0]] * len(x_vals)
        # Negative values (e.g. declining pct) get a muted red
        bar_colors = ["#ef4444" if v < 0 else CHART_COLORS[0] for v in y_vals]
        bars = ax.bar(range(len(x_vals)), y_vals, color=bar_colors, zorder=3, width=0.65)
        ax.set_xticks(range(len(x_vals)))
        ax.set_xticklabels(x_vals, rotation=40, ha="right", fontsize=7.5, color="#71717a")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.tick_params(axis="y", labelsize=7.5, colors="#71717a")
        ax.tick_params(axis="x", length=0)
        ax.tick_params(axis="y", length=0)
        ax.grid(axis="y", linestyle="--", linewidth=0.5, color="#e4e4e7", zorder=0)
        ax.set_axisbelow(True)

    elif chart_type == "pie_chart":
        fig_h_pie = width_px / dpi * 0.75
        plt.close(fig)
        fig, ax = plt.subplots(figsize=(fig_w, fig_h_pie))
        fig.patch.set_facecolor("white")
        wedge_colors = [CHART_COLORS[i % len(CHART_COLORS)] for i in range(len(x_vals))]
        wedges, texts, autotexts = ax.pie(
            y_vals,
            labels=x_vals,
            colors=wedge_colors,
            autopct="%1.1f%%",
            startangle=90,
            wedgeprops={"linewidth": 0},
            textprops={"fontsize": 9},
        )
        for at in autotexts:
            at.set_color("white")
            at.set_fontweight("bold")
            at.set_fontsize(8)
        ax.set_aspect("equal")

    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# PDF document builder
# ---------------------------------------------------------------------------

def build_insight_pdf(
    question: str,
    answer: str,
    chart_payload: Optional[dict],
    tool_calls: list[str],
    sources: list[dict],
    limitations: list[str],
    created_at: str,
    supplier_name: str,
) -> bytes:
    """
    Build a polished A4 PDF report for one saved insight.
    Returns raw PDF bytes.
    """
    buf = io.BytesIO()

    PAGE_W, PAGE_H = A4
    MARGIN_L = 2 * cm
    MARGIN_R = 2 * cm
    MARGIN_T = 3.5 * cm   # space for header band
    MARGIN_B = 2.2 * cm   # space for footer

    styles = getSampleStyleSheet()

    S_LABEL = ParagraphStyle(
        "label",
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=10,
        textColor=ZINC_500,
        spaceAfter=2,
        spaceBefore=10,
        letterSpacing=0.8,
    )
    S_QUESTION = ParagraphStyle(
        "question",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=ZINC_800,
        spaceAfter=6,
    )
    S_BODY = ParagraphStyle(
        "body",
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=ZINC_800,
        spaceAfter=4,
    )
    S_SMALL = ParagraphStyle(
        "small",
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=ZINC_500,
    )
    S_WARN = ParagraphStyle(
        "warn",
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=AMBER_600,
    )
    S_CHART_TITLE = ParagraphStyle(
        "chart_title",
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=13,
        textColor=ZINC_800,
        spaceAfter=2,
        spaceBefore=4,
    )
    S_CHART_DESC = ParagraphStyle(
        "chart_desc",
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=ZINC_500,
        spaceAfter=4,
    )

    # ------------------------------------------------------------------
    # Header + footer callbacks
    # ------------------------------------------------------------------
    export_ts = _fmt_date(created_at)
    now_ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def _draw_header(canvas, doc):
        canvas.saveState()
        # Header band background
        band_h = 1.8 * cm
        canvas.setFillColor(SLATE_900)
        canvas.rect(0, PAGE_H - band_h, PAGE_W, band_h, fill=1, stroke=0)
        # Brand mark
        canvas.setFillColor(BRAND_BLUE)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(MARGIN_L, PAGE_H - band_h + 0.65 * cm, "◈ Solvigo Sales Intelligence")
        # Supplier name (right-aligned)
        if supplier_name:
            canvas.setFillColor(WHITE)
            canvas.setFont("Helvetica", 8.5)
            canvas.drawRightString(PAGE_W - MARGIN_R, PAGE_H - band_h + 0.65 * cm, supplier_name)
        # Sub-label row
        canvas.setFillColor(HexColor("#64748b"))
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(MARGIN_L, PAGE_H - band_h + 0.25 * cm, "Analysrapport")
        canvas.restoreState()

    def _draw_footer(canvas, doc):
        canvas.saveState()
        # Separator line
        canvas.setStrokeColor(ZINC_200)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN_L, MARGIN_B, PAGE_W - MARGIN_R, MARGIN_B)
        # Footer text
        canvas.setFillColor(ZINC_500)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(
            MARGIN_L, MARGIN_B - 5 * mm,
            "Baserat på MCP-analytiklagret · Inte simulerade data · Solvigo Sales Intelligence",
        )
        canvas.drawRightString(PAGE_W - MARGIN_R, MARGIN_B - 5 * mm, now_ts)
        canvas.restoreState()

    def _on_page(canvas, doc):
        _draw_header(canvas, doc)
        _draw_footer(canvas, doc)

    # ------------------------------------------------------------------
    # Document template
    # ------------------------------------------------------------------
    frame = Frame(
        MARGIN_L, MARGIN_B + 6 * mm,
        PAGE_W - MARGIN_L - MARGIN_R,
        PAGE_H - MARGIN_T - MARGIN_B - 6 * mm,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    template = PageTemplate(id="main", frames=[frame], onPage=_on_page)
    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        pageTemplates=[template],
        leftMargin=MARGIN_L, rightMargin=MARGIN_R,
        topMargin=MARGIN_T, bottomMargin=MARGIN_B + 6 * mm,
    )

    # ------------------------------------------------------------------
    # Story content
    # ------------------------------------------------------------------
    story = []
    content_w = PAGE_W - MARGIN_L - MARGIN_R

    # Meta row: question as title + date
    story.append(Paragraph(question, S_QUESTION))
    story.append(Paragraph(f"Exporterad: {export_ts}", S_SMALL))
    story.append(Spacer(1, 0.4 * cm))

    # Divider
    story.append(Table(
        [[""]],
        colWidths=[content_w],
        style=TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, ZINC_200),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]),
    ))
    story.append(Spacer(1, 0.35 * cm))

    # Question section
    story.append(Paragraph("FRÅGA", S_LABEL))
    story.append(Paragraph(question, S_BODY))
    story.append(Spacer(1, 0.3 * cm))

    # Answer section
    story.append(Paragraph("ANALYS", S_LABEL))
    # Convert markdown-ish line breaks to reportlab-safe text
    answer_clean = answer.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for line in answer_clean.splitlines():
        if line.strip():
            story.append(Paragraph(line, S_BODY))
    story.append(Spacer(1, 0.3 * cm))

    # Chart section
    if chart_payload:
        chart_title = chart_payload.get("title", "")
        chart_desc  = chart_payload.get("description", "")
        try:
            png_bytes = _render_chart_png(chart_payload)
            chart_w = content_w
            # Pie charts are rendered slightly squarish; others 16:6.4 ratio
            if chart_payload.get("chart_type") == "pie_chart":
                chart_h = chart_w * 0.55
            else:
                chart_h = chart_w * 0.40
            img_buf = io.BytesIO(png_bytes)
            story.append(Paragraph(chart_title, S_CHART_TITLE))
            if chart_desc:
                story.append(Paragraph(chart_desc, S_CHART_DESC))
            story.append(Image(img_buf, width=chart_w, height=chart_h))
            story.append(Spacer(1, 0.35 * cm))
        except Exception:
            # Chart render failure degrades gracefully — omit chart block
            story.append(Paragraph("[Graf ej tillgänglig i denna export]", S_SMALL))
            story.append(Spacer(1, 0.35 * cm))

    # Sources section
    if tool_calls:
        story.append(Paragraph("DATAKÄLLOR", S_LABEL))
        for t in tool_calls:
            story.append(Paragraph(f"• {_tool_label(t)}", S_BODY))
        story.append(Spacer(1, 0.2 * cm))

    # Limitations section
    if limitations:
        story.append(Spacer(1, 0.1 * cm))
        story.append(Paragraph("BEGRÄNSNINGAR", S_LABEL))
        for lim in limitations:
            story.append(Paragraph(f"⚠ {lim}", S_WARN))

    doc.build(story)
    buf.seek(0)
    return buf.read()
