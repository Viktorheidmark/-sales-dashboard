"""
Saved-insight endpoints.

All operations are scoped to the authenticated supplier derived from the
session cookie. The frontend never sends supplier_id; the backend always
derives it from the JWT. Cross-supplier access returns 404, not 403.
"""

import csv
import io
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_supplier_id, get_current_user
from app.models.saved_insight import SavedInsight
from app.services.pdf_builder import build_insight_pdf
from app.schemas.insights import (
    InsightDetail,
    InsightSummary,
    SaveInsightRequest,
    SaveInsightResponse,
)

router = APIRouter(prefix="/api/insights", tags=["insights"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_supplier_uuid(supplier_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(supplier_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid supplier_id in session")


def _get_owned(insight_id: str, supplier_id: str, db: Session) -> SavedInsight:
    """Return insight only if owned by this supplier. Always raises 404 on miss."""
    try:
        iid = uuid.UUID(insight_id)
        sid = uuid.UUID(supplier_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Insight not found")

    row = (
        db.query(SavedInsight)
        .filter(SavedInsight.id == iid, SavedInsight.supplier_id == sid)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Insight not found")
    return row


def _to_detail(row: SavedInsight) -> InsightDetail:
    dq = row.data_quality or {}
    return InsightDetail(
        id=str(row.id),
        question=row.question,
        answer=row.answer,
        chart=row.chart_payload,
        tool_calls=dq.get("tool_calls", []),
        sources=dq.get("sources", []),
        limitations=dq.get("limitations", []),
        created_at=row.created_at.isoformat(),
    )


def _safe_filename_id(row_id: uuid.UUID) -> str:
    return str(row_id).replace("-", "")[:12]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=SaveInsightResponse, status_code=201)
def save_insight(
    req: SaveInsightRequest,
    db: Session = Depends(get_db),
    supplier_id: str = Depends(get_current_supplier_id),
):
    """Save a grounded chat insight for the authenticated supplier."""
    sid = _parse_supplier_uuid(supplier_id)

    row = SavedInsight(
        supplier_id=sid,
        question=req.question,
        answer=req.answer,
        chart_payload=req.chart,
        data_quality={
            "tool_calls": req.tool_calls,
            "sources": req.sources,
            "limitations": req.limitations,
        },
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return SaveInsightResponse(id=str(row.id), created_at=row.created_at.isoformat())


@router.get("", response_model=list[InsightSummary])
def list_insights(
    limit: int = 20,
    db: Session = Depends(get_db),
    supplier_id: str = Depends(get_current_supplier_id),
):
    """List saved insights for the authenticated supplier, newest first."""
    limit = max(1, min(limit, 100))
    sid = _parse_supplier_uuid(supplier_id)

    rows = (
        db.query(SavedInsight)
        .filter(SavedInsight.supplier_id == sid)
        .order_by(SavedInsight.created_at.desc())
        .limit(limit)
        .all()
    )

    summaries = []
    for row in rows:
        dq = row.data_quality or {}
        preview = row.answer[:160] + ("…" if len(row.answer) > 160 else "")
        summaries.append(
            InsightSummary(
                id=str(row.id),
                question=row.question,
                answer_preview=preview,
                created_at=row.created_at.isoformat(),
                has_chart=row.chart_payload is not None,
                source_tools=dq.get("tool_calls", []),
            )
        )
    return summaries


@router.get("/{insight_id}", response_model=InsightDetail)
def get_insight(
    insight_id: str,
    db: Session = Depends(get_db),
    supplier_id: str = Depends(get_current_supplier_id),
):
    """Return full saved insight. Returns 404 if not owned by authenticated supplier."""
    return _to_detail(_get_owned(insight_id, supplier_id, db))


@router.delete("/{insight_id}", status_code=204)
def delete_insight(
    insight_id: str,
    db: Session = Depends(get_db),
    supplier_id: str = Depends(get_current_supplier_id),
):
    """Delete a saved insight. Returns 404 if not owned by authenticated supplier."""
    row = _get_owned(insight_id, supplier_id, db)
    db.delete(row)
    db.commit()


@router.get("/{insight_id}/export.json")
def export_json(
    insight_id: str,
    db: Session = Depends(get_db),
    supplier_id: str = Depends(get_current_supplier_id),
):
    """
    Download the full insight as JSON. Strips supplier_id from source metadata
    so no internal identifiers are embedded in the export file.
    """
    row = _get_owned(insight_id, supplier_id, db)
    dq = row.data_quality or {}

    # Strip supplier_id from each source entry before exporting
    safe_sources = [
        {k: v for k, v in s.items() if k != "supplier_id"}
        for s in dq.get("sources", [])
    ]

    payload = {
        "question": row.question,
        "answer": row.answer,
        "chart": row.chart_payload,
        "tool_calls": dq.get("tool_calls", []),
        "sources": safe_sources,
        "limitations": dq.get("limitations", []),
        "created_at": row.created_at.isoformat(),
    }

    content = json.dumps(payload, ensure_ascii=False, indent=2)
    fname = f"insight-{_safe_filename_id(row.id)}.json"

    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/{insight_id}/export.csv")
def export_csv(
    insight_id: str,
    db: Session = Depends(get_db),
    supplier_id: str = Depends(get_current_supplier_id),
):
    """
    Download chart data rows as CSV. Returns 400 if the insight has no chart.
    Only primitive-valued columns are included (str, int, float, None).
    """
    row = _get_owned(insight_id, supplier_id, db)

    chart = row.chart_payload
    if not chart:
        raise HTTPException(status_code=400, detail="This insight has no chart data to export as CSV.")

    data: list[dict] = chart.get("data") or []
    if not data:
        raise HTTPException(status_code=400, detail="Chart data is empty.")

    # Derive fieldnames from the first row, keeping only primitive-safe values
    fieldnames = [
        k for k, v in data[0].items()
        if isinstance(v, (str, int, float, type(None)))
    ]

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(data)

    fname = f"insight-{_safe_filename_id(row.id)}-chart.csv"

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/{insight_id}/export.pdf")
def export_pdf(
    insight_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Generate and download a polished A4 PDF report for the insight.
    Chart is rendered from the saved chart_payload — never from AI prose.
    Returns 404 if not owned by authenticated supplier.
    """
    supplier_id = user["supplier_id"]
    supplier_name = user.get("supplier_name", "")
    row = _get_owned(insight_id, supplier_id, db)
    dq = row.data_quality or {}

    pdf_bytes = build_insight_pdf(
        question=row.question,
        answer=row.answer,
        chart_payload=row.chart_payload,
        tool_calls=dq.get("tool_calls", []),
        sources=dq.get("sources", []),
        limitations=dq.get("limitations", []),
        created_at=row.created_at.isoformat(),
        supplier_name=supplier_name,
    )

    date_str = row.created_at.strftime("%Y-%m-%d")
    fname = f"solvigo-insight-{date_str}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
