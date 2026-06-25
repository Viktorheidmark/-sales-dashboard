"""
Analytics service — adapter between FastAPI and the MCP query layer.

FastAPI routers call functions here. This module calls mcp_server.query_helpers
directly (sharing the same parameterised, supplier-scoped query functions).

This is NOT an MCP client — it does not use MCP transport. The MCP server
(mcp_server/server.py) remains the transport-facing entry point for LLM agents.
FastAPI uses the underlying query functions directly, which is the intended
architecture for the dashboard API layer.
"""

import sys
import uuid
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

# mcp_server/ lives at the project root, one level above backend/
_project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# backend/ must also be importable for mcp_server.db to find app.models
_backend_root = _project_root / "backend"
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from mcp_server.db import get_session
from mcp_server.query_helpers import (
    query_data_status,
    query_declining_products,
    query_market_share,
    query_revenue_drivers,
    query_sales_by_region,
    query_sales_over_time,
    query_supplier_kpis,
    query_supplier_product_assortment,
    query_top_products,
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_supplier_id(supplier_id: str) -> str:
    try:
        return str(uuid.UUID(supplier_id))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail=f"Invalid supplier_id '{supplier_id}'. Must be a UUID.")


def _parse_date(value: Optional[str], field: str) -> Optional[date]:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid {field} '{value}'. Expected YYYY-MM-DD.")


def _validate_granularity(granularity: str) -> str:
    if granularity not in ("day", "week", "month"):
        raise HTTPException(status_code=422, detail="granularity must be 'day', 'week', or 'month'.")
    return granularity


def _validate_limit(limit: int, max_val: int = 50) -> int:
    if not (1 <= limit <= max_val):
        raise HTTPException(status_code=422, detail=f"limit must be between 1 and {max_val}.")
    return limit


def _validate_days(days: int) -> int:
    if not (1 <= days <= 365):
        raise HTTPException(status_code=422, detail="days must be between 1 and 365.")
    return days


def _validate_category(category_name: str) -> str:
    if not category_name or not category_name.strip():
        raise HTTPException(status_code=422, detail="category_name must not be empty.")
    return category_name.strip()


# ---------------------------------------------------------------------------
# Service functions — one per endpoint
# ---------------------------------------------------------------------------

def get_supplier_list() -> list[dict]:
    """Return all suppliers with id and name."""
    from sqlalchemy import text
    db = get_session()
    try:
        rows = db.execute(text("SELECT id, name FROM suppliers ORDER BY name")).fetchall()
        return [{"id": str(r.id), "name": r.name} for r in rows]
    finally:
        db.close()


def get_overview(
    supplier_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    sid = _validate_supplier_id(supplier_id)
    sd = _parse_date(start_date, "start_date")
    ed = _parse_date(end_date, "end_date")
    db = get_session()
    try:
        return query_supplier_kpis(db, sid, sd, ed)
    finally:
        db.close()


def get_sales_over_time(
    supplier_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    granularity: str = "month",
) -> dict:
    sid = _validate_supplier_id(supplier_id)
    gran = _validate_granularity(granularity)
    sd = _parse_date(start_date, "start_date")
    ed = _parse_date(end_date, "end_date")
    db = get_session()
    try:
        return query_sales_over_time(db, sid, sd, ed, gran)
    finally:
        db.close()


def get_top_products(
    supplier_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 5,
    region: Optional[str] = None,
) -> dict:
    sid = _validate_supplier_id(supplier_id)
    lim = _validate_limit(limit)
    sd = _parse_date(start_date, "start_date")
    ed = _parse_date(end_date, "end_date")
    db = get_session()
    try:
        return query_top_products(db, sid, sd, ed, lim, region)
    finally:
        db.close()


def get_sales_by_region(
    supplier_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    sid = _validate_supplier_id(supplier_id)
    sd = _parse_date(start_date, "start_date")
    ed = _parse_date(end_date, "end_date")
    db = get_session()
    try:
        return query_sales_by_region(db, sid, sd, ed)
    finally:
        db.close()


def get_product_assortment(
    supplier_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    sid = _validate_supplier_id(supplier_id)
    sd = _parse_date(start_date, "start_date")
    ed = _parse_date(end_date, "end_date")
    db = get_session()
    try:
        return query_supplier_product_assortment(db, sid, sd, ed)
    finally:
        db.close()


def get_market_share(
    supplier_id: str,
    category_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    sid = _validate_supplier_id(supplier_id)
    cat = _validate_category(category_name)
    sd = _parse_date(start_date, "start_date")
    ed = _parse_date(end_date, "end_date")
    db = get_session()
    try:
        return query_market_share(db, sid, cat, sd, ed)
    finally:
        db.close()


def get_declining_products(
    supplier_id: str,
    days: int = 30,
    limit: int = 5,
) -> dict:
    sid = _validate_supplier_id(supplier_id)
    d = _validate_days(days)
    lim = _validate_limit(limit)
    db = get_session()
    try:
        return query_declining_products(db, sid, d, lim)
    finally:
        db.close()


def get_revenue_drivers(
    supplier_id: str,
    days: int = 30,
    limit: int = 5,
) -> dict:
    sid = _validate_supplier_id(supplier_id)
    d = _validate_days(days)
    lim = _validate_limit(limit, max_val=20)
    db = get_session()
    try:
        return query_revenue_drivers(db, sid, d, lim)
    finally:
        db.close()


def get_data_status(
    supplier_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    sid = _validate_supplier_id(supplier_id)
    sd = _parse_date(start_date, "start_date")
    ed = _parse_date(end_date, "end_date")
    db = get_session()
    try:
        return query_data_status(db, sid, sd, ed)
    finally:
        db.close()
