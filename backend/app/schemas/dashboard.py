from typing import Any, Optional
from pydantic import BaseModel


class DateRange(BaseModel):
    start: str
    end: str


class Metadata(BaseModel):
    source: str
    supplier_id: str
    generated_at: str
    date_range: Optional[DateRange] = None
    row_count: int
    limitations: list[str]


# --- /api/suppliers ---

class SupplierItem(BaseModel):
    id: str
    name: str


class SuppliersResponse(BaseModel):
    suppliers: list[SupplierItem]


# --- /api/dashboard/overview ---

class OverviewResponse(BaseModel):
    supplier_id: str
    total_revenue: Optional[float]
    total_orders: int
    total_units: int
    average_order_value: Optional[float]
    latest_order_date: Optional[str] = None
    date_range: DateRange
    prev_total_revenue: Optional[float] = None
    prev_total_orders: Optional[int] = None
    prev_total_units: Optional[int] = None
    prev_average_order_value: Optional[float] = None
    prev_date_range: Optional[DateRange] = None
    source: str
    generated_at: str
    row_count: int
    limitations: list[str]


# --- /api/dashboard/data-status ---

class DataStatusResponse(BaseModel):
    supplier_id: str
    period_start: str
    period_end: str
    latest_order_date: Optional[str]
    total_orders: int
    total_units: int
    generated_at: str
    limitations: list[str]


# --- /api/dashboard/sales-over-time ---

class TimeSeriesPoint(BaseModel):
    period: str
    revenue: Optional[float]
    orders: int
    units: int


class SalesOverTimeResponse(BaseModel):
    supplier_id: str
    granularity: str
    series: list[TimeSeriesPoint]
    date_range: DateRange
    source: str
    generated_at: str
    row_count: int
    limitations: list[str]


# --- /api/dashboard/top-products ---

class ProductItem(BaseModel):
    rank: int
    product_name: str
    sku: str
    revenue: Optional[float]
    units: int


class TopProductsResponse(BaseModel):
    supplier_id: str
    region_filter: Optional[str]
    products: list[ProductItem]
    date_range: DateRange
    source: str
    generated_at: str
    row_count: int
    limitations: list[str]


# --- /api/dashboard/products ---

class AssortmentProductItem(BaseModel):
    product_id: str
    product_name: str
    sku: str
    revenue: float
    units: int
    average_sale_price_per_unit: Optional[float] = None


class ProductAssortmentResponse(BaseModel):
    supplier_id: str
    products: list[AssortmentProductItem]
    date_range: DateRange
    source: str
    generated_at: str
    row_count: int
    limitations: list[str]


# --- /api/dashboard/regions ---

class RegionItem(BaseModel):
    rank: int
    region: str
    revenue: Optional[float]
    orders: int
    units: int


class RegionsResponse(BaseModel):
    supplier_id: str
    regions: list[RegionItem]
    date_range: DateRange
    source: str
    generated_at: str
    row_count: int
    limitations: list[str]


# --- /api/dashboard/market-share ---

class MarketShareResponse(BaseModel):
    supplier_id: str
    category_name: str
    supplier_revenue: float
    category_total_revenue: float
    market_share_pct: float
    competitor_aggregate_revenue: Optional[float]
    competitor_count: int
    supplier_rank: Optional[int] = None
    total_suppliers: Optional[int] = None
    prev_market_share_pct: Optional[float] = None
    prev_date_range: Optional[DateRange] = None
    date_range: DateRange
    source: str
    generated_at: str
    row_count: int
    limitations: list[str]


# --- /api/dashboard/declining-products ---

class DecliningProductItem(BaseModel):
    rank: int
    product_name: str
    sku: str
    latest_period_revenue: float
    prior_period_revenue: float
    revenue_change: float
    revenue_change_pct: Optional[float]


class DecliningProductsResponse(BaseModel):
    supplier_id: str
    comparison_days: int
    latest_period: DateRange
    prior_period: DateRange
    products: list[DecliningProductItem]
    source: str
    generated_at: str
    row_count: int
    limitations: list[str]
