export interface DateRange {
  start: string
  end: string
}

// --- /api/auth ---

export interface AuthUser {
  supplier_id: string
  supplier_name: string
  email: string
}

// --- /api/chat ---

export interface SourceMeta {
  tool: string
  source: string
  supplier_id: string
  generated_at: string
  row_count?: number
  date_range?: DateRange
  comparison_period_label?: string
  limitations?: string[]
}

export interface ChartHighlights {
  peak_label: string
  peak_revenue: number
  peak_label_display?: string
  trough_label: string
  trough_revenue: number
  trough_label_display?: string
  first_revenue: number
  last_revenue: number
  avg_revenue?: number
  change_pct: number
  granularity?: string
}

export interface ChartPayload {
  chart_type: 'line_chart' | 'bar_chart' | 'pie_chart' | 'insight_card' | 'empty_state'
  title: string
  description: string
  data: Record<string, unknown>[]
  x_key: string
  y_key: string
  source_tool: string
  generated_from_row_count: number
  layout?: 'horizontal' | 'vertical'
  period_note?: string
  emphasis_index?: number
  tooltip_key?: string
  highlights?: ChartHighlights
  show_markers?: boolean
  y_axis_from_zero?: boolean
  trend_granularity?: string
  chart_variant?: 'decline_comparison' | 'decline_trend' | 'decline_ranking'
  chart_role?: 'primary' | 'secondary'
  compact?: boolean
  stability_note?: string
  period_split_at?: string
  period_split_label?: string
  prior_period_label?: string
  latest_period_label?: string
  decline_metrics?: {
    prior_revenue?: number
    latest_revenue?: number
    revenue_change?: number
    revenue_change_pct?: number | null
  }
}

export interface DeepDivePeriodTotals {
  start?: string
  end?: string
  total_revenue: number
  total_orders: number
  total_units: number
}

export interface DeepDiveDriver {
  rank: number
  product_name?: string
  region?: string
  current_period_revenue: number
  prior_period_revenue: number
  revenue_change: number
  revenue_change_pct?: number | null
}

export interface DeepDivePeriodSummary {
  current: DeepDivePeriodTotals
  prior: DeepDivePeriodTotals
  revenue_change: number
  revenue_change_pct: number | null
  orders_change: number
  units_change: number
}

export interface DeepDivePayload {
  kind: 'revenue_development' | 'product_decline'
  comparison_days: number
  period_summary: DeepDivePeriodSummary | null
  top_gainers?: DeepDiveDriver[]
  top_losers?: DeepDiveDriver[]
  strongest_region?: DeepDiveDriver | null
  weakest_region?: DeepDiveDriver | null
  focus_product?: {
    product_name: string
    sku?: string
    top_regions?: DeepDiveDriver[]
  } | null
  portfolio_comparison?: DeepDiveDriver[]
  relatively_stable?: boolean
}

export interface FollowUpAction {
  label: string
  message: string
  action?: string
  context?: {
    start_date?: string
    end_date?: string
    period_kind?: string
    granularity?: string
    region?: string
    category?: string
  }
}

export interface AnalysisContext {
  prior_intent?: string
  start_date?: string
  end_date?: string
  period_kind?: string
  granularity?: string
  region?: string
  category?: string
  product_name?: string
  limit?: number
  prior_tool_calls?: string[]
  awaiting_decline_period?: boolean
}

export interface PriorTurnContext {
  question: string
  answer?: string
  tool_calls: string[]
  sources?: SourceMeta[]
  has_chart?: boolean
  analysis_context?: AnalysisContext
}

export interface ChatRequest {
  message: string
  start_date?: string
  end_date?: string
  prior_context?: PriorTurnContext
  follow_up_action?: FollowUpAction
}

// --- /api/insights ---

export interface SaveInsightRequest {
  question: string
  answer: string
  chart?: ChartPayload | null
  tool_calls: string[]
  sources: SourceMeta[]
  limitations: string[]
}

export interface SaveInsightResponse {
  id: string
  created_at: string
}

export interface InsightSummary {
  id: string
  question: string
  answer_preview: string
  created_at: string
  has_chart: boolean
  source_tools: string[]
}

export interface InsightDetail {
  id: string
  question: string
  answer: string
  chart?: ChartPayload | null
  tool_calls: string[]
  sources: Record<string, unknown>[]
  limitations: string[]
  created_at: string
}

export interface ChatResponse {
  answer: string
  tool_calls: string[]
  sources: SourceMeta[]
  chart?: ChartPayload | null
  charts?: ChartPayload[]
  deep_dive?: DeepDivePayload | null
  follow_up_actions?: FollowUpAction[]
  analysis_context?: AnalysisContext | null
  limitations: string[]
  supplier_id: string
  generated_at: string
  response_kind?: 'conversational' | 'insufficient_data' | 'unsupported'
}

// --- /api/chat/stream SSE events ---

export type StreamEvent =
  | { type: 'status'; text: string }
  | { type: 'delta'; text: string }
  | { type: 'complete' } & ChatResponse
  | { type: 'error'; message: string }

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
  latest_order_date: string | null
  date_range: DateRange
  prev_total_revenue: number | null
  prev_total_orders: number | null
  prev_total_units: number | null
  prev_average_order_value: number | null
  prev_date_range: DateRange | null
  source: string
  generated_at: string
  row_count: number
  limitations: string[]
}

export interface DataStatusResponse {
  supplier_id: string
  period_start: string
  period_end: string
  latest_order_date: string | null
  total_orders: number
  total_units: number
  generated_at: string
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
