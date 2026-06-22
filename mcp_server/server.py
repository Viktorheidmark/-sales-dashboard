"""
Solvigo MCP Analytics Server.

Exposes six supplier-scoped retail analytics tools backed by Neon PostgreSQL.
The LLM never accesses the database directly — all queries run through
parameterised SQLAlchemy functions in query_helpers.py.

Run with:
    cd <project_root>
    python -m mcp_server.server          # stdio transport (for MCP clients)
    fastmcp dev mcp_server/server.py     # interactive inspector (browser UI)
"""

from datetime import date
from typing import Optional

from mcp.server.fastmcp import FastMCP

from mcp_server.db import get_session
from mcp_server.query_helpers import (
    query_declining_products,
    query_market_share,
    query_sales_by_region,
    query_sales_over_time,
    query_supplier_kpis,
    query_top_products,
)

mcp = FastMCP("solvigo-analytics")


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------

def _parse_date(value: Optional[str], field: str) -> Optional[date]:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"Invalid {field}: '{value}'. Expected ISO format YYYY-MM-DD.")


def _validate_supplier_id(supplier_id: str) -> str:
    import uuid as _uuid
    try:
        return str(_uuid.UUID(supplier_id))
    except ValueError:
        raise ValueError(f"Invalid supplier_id: '{supplier_id}'. Must be a valid UUID.")


# ---------------------------------------------------------------------------
# Tool 1 — KPIs
# ---------------------------------------------------------------------------

@mcp.tool()
def get_supplier_kpis(
    supplier_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """
    Return aggregate KPIs for a supplier over an optional date range.

    Returns total_revenue, total_orders, total_units, average_order_value,
    date_range, and source metadata.

    supplier_id must be a valid UUID matching a row in the suppliers table.
    Dates must be ISO format (YYYY-MM-DD). Defaults to the last 180 days.
    """
    sid = _validate_supplier_id(supplier_id)
    sd = _parse_date(start_date, "start_date")
    ed = _parse_date(end_date, "end_date")

    db = get_session()
    try:
        return query_supplier_kpis(db, sid, sd, ed)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 2 — Sales over time
# ---------------------------------------------------------------------------

@mcp.tool()
def get_sales_over_time(
    supplier_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    granularity: str = "month",
) -> dict:
    """
    Return a time series of revenue, orders, and units for a supplier.

    granularity must be one of: day, week, month.
    Returns an ordered list of {period, revenue, orders, units} plus metadata.
    """
    sid = _validate_supplier_id(supplier_id)
    sd = _parse_date(start_date, "start_date")
    ed = _parse_date(end_date, "end_date")
    if granularity not in ("day", "week", "month"):
        raise ValueError("granularity must be 'day', 'week', or 'month'.")

    db = get_session()
    try:
        return query_sales_over_time(db, sid, sd, ed, granularity)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 3 — Top products
# ---------------------------------------------------------------------------

@mcp.tool()
def get_top_products(
    supplier_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 5,
    region: Optional[str] = None,
) -> dict:
    """
    Return the top-selling products by revenue for a supplier.

    Optionally filter by region name (e.g. 'Stockholm').
    limit defaults to 5, max 50.
    Returns rank, product_name, sku, revenue, units, and metadata.
    """
    sid = _validate_supplier_id(supplier_id)
    sd = _parse_date(start_date, "start_date")
    ed = _parse_date(end_date, "end_date")
    if not (1 <= limit <= 50):
        raise ValueError("limit must be between 1 and 50.")

    db = get_session()
    try:
        return query_top_products(db, sid, sd, ed, limit, region)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 4 — Sales by region
# ---------------------------------------------------------------------------

@mcp.tool()
def get_sales_by_region(
    supplier_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """
    Return revenue, orders, and units broken down by region for a supplier.

    Regions are ranked by revenue descending.
    Returns a list of {rank, region, revenue, orders, units} plus metadata.
    """
    sid = _validate_supplier_id(supplier_id)
    sd = _parse_date(start_date, "start_date")
    ed = _parse_date(end_date, "end_date")

    db = get_session()
    try:
        return query_sales_by_region(db, sid, sd, ed)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 5 — Market share
# ---------------------------------------------------------------------------

@mcp.tool()
def get_market_share(
    supplier_id: str,
    category_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """
    Return this supplier's revenue share within a product category.

    category_name must match a name in the categories table (e.g. 'Mejeri').
    Competitor data is aggregate-only — no competitor product names, SKUs,
    order IDs, or customer data are exposed.

    Returns supplier_revenue, category_total_revenue, market_share_pct,
    competitor_aggregate_revenue, competitor_count, and metadata.
    """
    sid = _validate_supplier_id(supplier_id)
    if not category_name or not category_name.strip():
        raise ValueError("category_name must not be empty.")
    sd = _parse_date(start_date, "start_date")
    ed = _parse_date(end_date, "end_date")

    db = get_session()
    try:
        return query_market_share(db, sid, category_name.strip(), sd, ed)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 6 — Declining products
# ---------------------------------------------------------------------------

@mcp.tool()
def get_declining_products(
    supplier_id: str,
    days: int = 30,
    limit: int = 5,
) -> dict:
    """
    Return products whose revenue declined most in the latest period vs the
    equally-sized prior period.

    days controls the comparison window (default 30, max 365).
    limit controls how many products to return (default 5, max 50).

    Returns rank, product_name, sku, latest_period_revenue,
    prior_period_revenue, revenue_change, revenue_change_pct, and metadata.
    """
    sid = _validate_supplier_id(supplier_id)
    if not (1 <= days <= 365):
        raise ValueError("days must be between 1 and 365.")
    if not (1 <= limit <= 50):
        raise ValueError("limit must be between 1 and 50.")

    db = get_session()
    try:
        return query_declining_products(db, sid, days, limit)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
