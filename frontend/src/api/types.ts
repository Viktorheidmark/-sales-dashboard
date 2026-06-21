export interface DateRange {
  start: string
  end: string
}

export interface SupplierItem {
  id: string
  name: string
}

export interface SuppliersResponse {
  suppliers: SupplierItem[]
}

export interface OverviewResponse {
  supplier_id: string
  total_revenue: number | null
  total_orders: number
  total_units: number
  average_order_value: number | null
  date_range: DateRange
  source: string
  generated_at: string
  row_count: number
  limitations: string[]
}

export interface TimeSeriesPoint {
  period: string
  revenue: number | null
  orders: number
  units: number
}

export interface SalesOverTimeResponse {
  supplier_id: string
  granularity: string
  series: TimeSeriesPoint[]
  date_range: DateRange
  source: string
  generated_at: string
  row_count: number
  limitations: string[]
}

export interface ProductItem {
  rank: number
  product_name: string
  sku: string
  revenue: number | null
  units: number
}

export interface TopProductsResponse {
  supplier_id: string
  region_filter: string | null
  products: ProductItem[]
  date_range: DateRange
  source: string
  generated_at: string
  row_count: number
  limitations: string[]
}

export interface RegionItem {
  rank: number
  region: string
  revenue: number | null
  orders: number
  units: number
}

export interface RegionsResponse {
  supplier_id: string
  regions: RegionItem[]
  date_range: DateRange
  source: string
  generated_at: string
  row_count: number
  limitations: string[]
}

export interface MarketShareResponse {
  supplier_id: string
  category_name: string
  supplier_revenue: number
  category_total_revenue: number
  market_share_pct: number
  competitor_aggregate_revenue: number | null
  competitor_count: number
  date_range: DateRange
  source: string
  generated_at: string
  row_count: number
  limitations: string[]
}

export interface DecliningProductItem {
  rank: number
  product_name: string
  sku: string
  latest_period_revenue: number
  prior_period_revenue: number
  revenue_change: number
  revenue_change_pct: number | null
}

export interface DecliningProductsResponse {
  supplier_id: string
  comparison_days: number
  latest_period: DateRange
  prior_period: DateRange
  products: DecliningProductItem[]
  source: string
  generated_at: string
  row_count: number
  limitations: string[]
}
