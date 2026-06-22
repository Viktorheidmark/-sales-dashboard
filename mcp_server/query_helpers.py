"""
Parameterised SQLAlchemy query functions for each MCP analytics tool.

Rules enforced here:
- Every query filters by supplier_id through the brands → products join chain.
  The caller cannot override or bypass this filter.
- Competitor data (get_market_share) is returned as aggregated totals only.
  No competitor product names, SKUs, order IDs, or customer data are exposed.
- No raw SQL strings. All queries use SQLAlchemy Core text() with named
  bind parameters, or ORM expressions.
- Input validation (dates, granularity, limits) is the caller's responsibility
  before reaching these functions, but each function also applies safe defaults.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session


def _date_range(start_date: Optional[date], end_date: Optional[date]) -> tuple[date, date]:
    today = datetime.now(tz=timezone.utc).date()
    return (start_date or (today - timedelta(days=179))), (end_date or today)


def _to_iso(d: date) -> str:
    return d.isoformat()


def _float(v) -> Optional[float]:
    if v is None:
        return None
    return float(Decimal(str(v)))


# ---------------------------------------------------------------------------
# 1. KPIs
# ---------------------------------------------------------------------------

def query_supplier_kpis(
    db: Session,
    supplier_id: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> dict:
    """
    Return aggregate KPIs for a supplier over a date range.

    Joins: order_items → products → brands (filtered by supplier_id)
           order_items → orders (filtered by order_date range)
    """
    sd, ed = _date_range(start_date, end_date)

    row = db.execute(
        text("""
            SELECT
                COALESCE(SUM(oi.revenue), 0)         AS total_revenue,
                COUNT(DISTINCT o.id)                  AS total_orders,
                COALESCE(SUM(oi.quantity), 0)         AS total_units,
                CASE WHEN COUNT(DISTINCT o.id) = 0
                     THEN 0
                     ELSE SUM(oi.revenue) / COUNT(DISTINCT o.id)
                END                                   AS average_order_value,
                MAX(o.order_date)                     AS latest_order_date
            FROM order_items oi
            JOIN orders  o ON o.id  = oi.order_id
            JOIN products p ON p.id = oi.product_id
            JOIN brands   b ON b.id = p.brand_id
            WHERE b.supplier_id = CAST(:supplier_id AS uuid)
              AND o.order_date >= :start_date
              AND o.order_date <  :end_date + INTERVAL '1 day'
        """),
        {"supplier_id": supplier_id, "start_date": sd, "end_date": ed},
    ).fetchone()

    return {
        "supplier_id": supplier_id,
        "total_revenue": _float(row.total_revenue),
        "total_orders": int(row.total_orders),
        "total_units": int(row.total_units),
        "average_order_value": _float(row.average_order_value),
        "latest_order_date": row.latest_order_date.date().isoformat() if row.latest_order_date else None,
        "date_range": {"start": _to_iso(sd), "end": _to_iso(ed)},
        "source": "MCP:get_supplier_kpis",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "row_count": 1,
        "limitations": [],
    }


# ---------------------------------------------------------------------------
# 2. Sales over time
# ---------------------------------------------------------------------------

_GRANULARITY_TRUNC = {
    "day":   "day",
    "week":  "week",
    "month": "month",
}


def query_sales_over_time(
    db: Session,
    supplier_id: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    granularity: str = "month",
) -> dict:
    """
    Return a time series of revenue bucketed by day, week, or month.
    """
    if granularity not in _GRANULARITY_TRUNC:
        granularity = "month"
    trunc = _GRANULARITY_TRUNC[granularity]
    sd, ed = _date_range(start_date, end_date)

    rows = db.execute(
        text(f"""
            SELECT
                DATE_TRUNC('{trunc}', o.order_date)::date AS period,
                COALESCE(SUM(oi.revenue), 0)              AS revenue,
                COUNT(DISTINCT o.id)                       AS orders,
                COALESCE(SUM(oi.quantity), 0)             AS units
            FROM order_items oi
            JOIN orders   o ON o.id  = oi.order_id
            JOIN products p ON p.id  = oi.product_id
            JOIN brands   b ON b.id  = p.brand_id
            WHERE b.supplier_id = CAST(:supplier_id AS uuid)
              AND o.order_date >= :start_date
              AND o.order_date <  :end_date + INTERVAL '1 day'
            GROUP BY period
            ORDER BY period
        """),
        {"supplier_id": supplier_id, "start_date": sd, "end_date": ed},
    ).fetchall()

    series = [
        {
            "period": str(r.period),
            "revenue": _float(r.revenue),
            "orders": int(r.orders),
            "units": int(r.units),
        }
        for r in rows
    ]

    return {
        "supplier_id": supplier_id,
        "granularity": granularity,
        "series": series,
        "date_range": {"start": _to_iso(sd), "end": _to_iso(ed)},
        "source": "MCP:get_sales_over_time",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "row_count": len(series),
        "limitations": [],
    }


# ---------------------------------------------------------------------------
# 3. Top products
# ---------------------------------------------------------------------------

def query_top_products(
    db: Session,
    supplier_id: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 5,
    region: Optional[str] = None,
) -> dict:
    """
    Return top products by revenue for a supplier, optionally filtered by region.
    """
    limit = max(1, min(limit, 50))
    sd, ed = _date_range(start_date, end_date)

    region_join = ""
    region_filter = ""
    params: dict = {"supplier_id": supplier_id, "start_date": sd, "end_date": ed, "limit": limit}

    if region:
        region_join = """
            JOIN customers cu ON cu.id = o.customer_id
            JOIN regions   r  ON r.id  = cu.region_id
        """
        region_filter = "AND r.name = :region"
        params["region"] = region

    rows = db.execute(
        text(f"""
            SELECT
                p.name                          AS product_name,
                p.sku                           AS sku,
                COALESCE(SUM(oi.revenue), 0)    AS revenue,
                COALESCE(SUM(oi.quantity), 0)   AS units,
                RANK() OVER (ORDER BY SUM(oi.revenue) DESC) AS rank
            FROM order_items oi
            JOIN orders   o ON o.id  = oi.order_id
            JOIN products p ON p.id  = oi.product_id
            JOIN brands   b ON b.id  = p.brand_id
            {region_join}
            WHERE b.supplier_id = CAST(:supplier_id AS uuid)
              AND o.order_date >= :start_date
              AND o.order_date <  :end_date + INTERVAL '1 day'
              {region_filter}
            GROUP BY p.id, p.name, p.sku
            ORDER BY revenue DESC
            LIMIT :limit
        """),
        params,
    ).fetchall()

    products = [
        {
            "rank": int(r.rank),
            "product_name": r.product_name,
            "sku": r.sku,
            "revenue": _float(r.revenue),
            "units": int(r.units),
        }
        for r in rows
    ]

    return {
        "supplier_id": supplier_id,
        "region_filter": region,
        "products": products,
        "date_range": {"start": _to_iso(sd), "end": _to_iso(ed)},
        "source": "MCP:get_top_products",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "row_count": len(products),
        "limitations": [],
    }


# ---------------------------------------------------------------------------
# 4. Sales by region
# ---------------------------------------------------------------------------

def query_sales_by_region(
    db: Session,
    supplier_id: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> dict:
    """
    Return revenue, orders, and units broken down by region for a supplier.
    """
    sd, ed = _date_range(start_date, end_date)

    rows = db.execute(
        text("""
            SELECT
                r.name                          AS region,
                COALESCE(SUM(oi.revenue), 0)    AS revenue,
                COUNT(DISTINCT o.id)             AS orders,
                COALESCE(SUM(oi.quantity), 0)   AS units,
                RANK() OVER (ORDER BY SUM(oi.revenue) DESC) AS rank
            FROM order_items oi
            JOIN orders    o  ON o.id  = oi.order_id
            JOIN products  p  ON p.id  = oi.product_id
            JOIN brands    b  ON b.id  = p.brand_id
            JOIN customers cu ON cu.id = o.customer_id
            JOIN regions   r  ON r.id  = cu.region_id
            WHERE b.supplier_id = CAST(:supplier_id AS uuid)
              AND o.order_date >= :start_date
              AND o.order_date <  :end_date + INTERVAL '1 day'
            GROUP BY r.name
            ORDER BY revenue DESC
        """),
        {"supplier_id": supplier_id, "start_date": sd, "end_date": ed},
    ).fetchall()

    regions = [
        {
            "rank": int(r.rank),
            "region": r.region,
            "revenue": _float(r.revenue),
            "orders": int(r.orders),
            "units": int(r.units),
        }
        for r in rows
    ]

    return {
        "supplier_id": supplier_id,
        "regions": regions,
        "date_range": {"start": _to_iso(sd), "end": _to_iso(ed)},
        "source": "MCP:get_sales_by_region",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "row_count": len(regions),
        "limitations": [],
    }


# ---------------------------------------------------------------------------
# 5. Market share
# ---------------------------------------------------------------------------

def query_market_share(
    db: Session,
    supplier_id: str,
    category_name: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> dict:
    """
    Return this supplier's revenue share within a category.

    Competitor data is returned as aggregate totals only — no competitor
    product names, SKUs, order IDs, or customer data are exposed.
    """
    sd, ed = _date_range(start_date, end_date)
    params = {"supplier_id": supplier_id, "category_name": category_name, "start_date": sd, "end_date": ed}

    row = db.execute(
        text("""
            SELECT
                COALESCE(SUM(CASE WHEN b.supplier_id = CAST(:supplier_id AS uuid)
                                  THEN oi.revenue ELSE 0 END), 0)  AS supplier_revenue,
                COALESCE(SUM(oi.revenue), 0)                        AS category_revenue,
                COUNT(DISTINCT CASE WHEN b.supplier_id != CAST(:supplier_id AS uuid)
                                    THEN b.supplier_id END)         AS competitor_count,
                COALESCE(SUM(CASE WHEN b.supplier_id != CAST(:supplier_id AS uuid)
                                  THEN oi.revenue ELSE 0 END), 0)  AS competitor_revenue
            FROM order_items oi
            JOIN orders    o   ON o.id   = oi.order_id
            JOIN products  p   ON p.id   = oi.product_id
            JOIN categories c  ON c.id   = p.category_id
            JOIN brands    b   ON b.id   = p.brand_id
            WHERE c.name = :category_name
              AND o.order_date >= :start_date
              AND o.order_date <  :end_date + INTERVAL '1 day'
        """),
        params,
    ).fetchone()

    cat_rev = _float(row.category_revenue) or 0.0
    sup_rev = _float(row.supplier_revenue) or 0.0
    share_pct = round(100.0 * sup_rev / cat_rev, 2) if cat_rev > 0 else 0.0

    return {
        "supplier_id": supplier_id,
        "category_name": category_name,
        "supplier_revenue": sup_rev,
        "category_total_revenue": cat_rev,
        "market_share_pct": share_pct,
        "competitor_aggregate_revenue": _float(row.competitor_revenue),
        "competitor_count": int(row.competitor_count),
        "date_range": {"start": _to_iso(sd), "end": _to_iso(ed)},
        "source": "MCP:get_market_share",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "row_count": 1,
        "limitations": [
            "Konkurrentdata visas endast aggregerat. Produkt-, order- och kunddetaljer visas inte."
        ],
    }


# ---------------------------------------------------------------------------
# 6. Declining products
# ---------------------------------------------------------------------------

def query_declining_products(
    db: Session,
    supplier_id: str,
    days: int = 30,
    limit: int = 5,
) -> dict:
    """
    Return products whose revenue declined most between the latest period
    and the equally-sized prior period.

    latest_period : [today - days,     today]
    prior_period  : [today - 2*days,   today - days)
    """
    days = max(1, min(days, 365))
    limit = max(1, min(limit, 50))
    today = datetime.now(tz=timezone.utc).date()
    latest_start = today - timedelta(days=days)
    prior_start = today - timedelta(days=days * 2)

    rows = db.execute(
        text("""
            SELECT
                p.name                                                          AS product_name,
                p.sku                                                           AS sku,
                COALESCE(SUM(CASE WHEN o.order_date >= :latest_start
                                  THEN oi.revenue ELSE 0 END), 0)              AS latest_revenue,
                COALESCE(SUM(CASE WHEN o.order_date >= :prior_start
                                   AND o.order_date <  :latest_start
                                  THEN oi.revenue ELSE 0 END), 0)              AS prior_revenue
            FROM order_items oi
            JOIN orders   o ON o.id  = oi.order_id
            JOIN products p ON p.id  = oi.product_id
            JOIN brands   b ON b.id  = p.brand_id
            WHERE b.supplier_id = CAST(:supplier_id AS uuid)
              AND o.order_date >= :prior_start
              AND o.order_date <  :today + INTERVAL '1 day'
            GROUP BY p.id, p.name, p.sku
            HAVING SUM(CASE WHEN o.order_date >= :latest_start
                            THEN oi.revenue ELSE 0 END)
                 < SUM(CASE WHEN o.order_date >= :prior_start
                             AND o.order_date <  :latest_start
                            THEN oi.revenue ELSE 0 END)
            ORDER BY (
                SUM(CASE WHEN o.order_date >= :latest_start THEN oi.revenue ELSE 0 END)
                - SUM(CASE WHEN o.order_date >= :prior_start AND o.order_date < :latest_start
                           THEN oi.revenue ELSE 0 END)
            ) ASC
            LIMIT :limit
        """),
        {
            "supplier_id": supplier_id,
            "today": today,
            "latest_start": latest_start,
            "prior_start": prior_start,
            "limit": limit,
        },
    ).fetchall()

    products = []
    for rank, r in enumerate(rows, start=1):
        latest = _float(r.latest_revenue) or 0.0
        prior = _float(r.prior_revenue) or 0.0
        change = latest - prior
        change_pct = round(100.0 * change / prior, 2) if prior > 0 else None
        products.append({
            "rank": rank,
            "product_name": r.product_name,
            "sku": r.sku,
            "latest_period_revenue": latest,
            "prior_period_revenue": prior,
            "revenue_change": round(change, 2),
            "revenue_change_pct": change_pct,
        })

    return {
        "supplier_id": supplier_id,
        "comparison_days": days,
        "latest_period": {"start": _to_iso(latest_start), "end": _to_iso(today)},
        "prior_period": {"start": _to_iso(prior_start), "end": _to_iso(latest_start)},
        "products": products,
        "source": "MCP:get_declining_products",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "row_count": len(products),
        "limitations": [],
    }


# ---------------------------------------------------------------------------
# 7. Data status
# ---------------------------------------------------------------------------

def query_data_status(
    db: Session,
    supplier_id: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> dict:
    """
    Return data-freshness metadata for a supplier over a date range:
    latest transaction date, period order/unit counts, and request timestamp.
    """
    sd, ed = _date_range(start_date, end_date)

    row = db.execute(
        text("""
            SELECT
                MAX(o.order_date)             AS latest_order_date,
                COUNT(DISTINCT o.id)          AS total_orders,
                COALESCE(SUM(oi.quantity), 0) AS total_units
            FROM order_items oi
            JOIN orders   o ON o.id  = oi.order_id
            JOIN products p ON p.id  = oi.product_id
            JOIN brands   b ON b.id  = p.brand_id
            WHERE b.supplier_id = CAST(:supplier_id AS uuid)
              AND o.order_date >= :start_date
              AND o.order_date <  :end_date + INTERVAL '1 day'
        """),
        {"supplier_id": supplier_id, "start_date": sd, "end_date": ed},
    ).fetchone()

    return {
        "supplier_id": supplier_id,
        "period_start": _to_iso(sd),
        "period_end": _to_iso(ed),
        "latest_order_date": row.latest_order_date.date().isoformat() if row.latest_order_date else None,
        "total_orders": int(row.total_orders),
        "total_units": int(row.total_units),
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "limitations": [],
    }
