from typing import Optional

from fastapi import APIRouter, Depends
from app.dependencies import get_current_supplier_id
from app.schemas.dashboard import (
    DataStatusResponse,
    DecliningProductsResponse,
    MarketShareResponse,
    OverviewResponse,
    ProductAssortmentResponse,
    RegionsResponse,
    SalesOverTimeResponse,
    TopProductsResponse,
)
from app.services import analytics

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=OverviewResponse)
def overview(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    supplier_id: str = Depends(get_current_supplier_id),
):
    """Aggregate KPIs for the authenticated supplier: revenue, orders, units, AOV."""
    return analytics.get_overview(supplier_id, start_date, end_date)


@router.get("/sales-over-time", response_model=SalesOverTimeResponse)
def sales_over_time(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    granularity: str = "month",
    supplier_id: str = Depends(get_current_supplier_id),
):
    """Revenue time series bucketed by day, week, or month."""
    return analytics.get_sales_over_time(supplier_id, start_date, end_date, granularity)


@router.get("/top-products", response_model=TopProductsResponse)
def top_products(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 5,
    region: Optional[str] = None,
    supplier_id: str = Depends(get_current_supplier_id),
):
    """Top products by revenue, optionally filtered by region."""
    return analytics.get_top_products(supplier_id, start_date, end_date, limit, region)


@router.get("/products", response_model=ProductAssortmentResponse)
def product_assortment(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    supplier_id: str = Depends(get_current_supplier_id),
):
    """All products in the supplier assortment with sales volume, revenue, and average sale price."""
    return analytics.get_product_assortment(supplier_id, start_date, end_date)


@router.get("/regions", response_model=RegionsResponse)
def regions(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    supplier_id: str = Depends(get_current_supplier_id),
):
    """Revenue, orders, and units broken down by region."""
    return analytics.get_sales_by_region(supplier_id, start_date, end_date)


@router.get("/market-share", response_model=MarketShareResponse)
def market_share(
    category_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    supplier_id: str = Depends(get_current_supplier_id),
):
    """Supplier revenue share within a product category. Competitor data is aggregate-only."""
    return analytics.get_market_share(supplier_id, category_name, start_date, end_date)


@router.get("/declining-products", response_model=DecliningProductsResponse)
def declining_products(
    days: int = 30,
    limit: int = 5,
    supplier_id: str = Depends(get_current_supplier_id),
):
    """Products with the largest revenue decline vs the prior equal-length period."""
    return analytics.get_declining_products(supplier_id, days, limit)


@router.get("/data-status", response_model=DataStatusResponse)
def data_status(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    supplier_id: str = Depends(get_current_supplier_id),
):
    """Data-freshness metadata: latest transaction date, period counts, request timestamp."""
    return analytics.get_data_status(supplier_id, start_date, end_date)
