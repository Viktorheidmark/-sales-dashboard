import type {
  ChatRequest,
  ChatResponse,
  DecliningProductsResponse,
  MarketShareResponse,
  OverviewResponse,
  RegionsResponse,
  SalesOverTimeResponse,
  SuppliersResponse,
  TopProductsResponse,
} from './types'

const BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

async function get<T>(path: string, params: Record<string, string | number | undefined> = {}): Promise<T> {
  const url = new URL(`${BASE}${path}`)
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') {
      url.searchParams.set(k, String(v))
    }
  }
  const res = await fetch(url.toString())
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail?.detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  getSuppliers: () =>
    get<SuppliersResponse>('/api/suppliers'),

  getOverview: (supplierId: string, startDate?: string, endDate?: string) =>
    get<OverviewResponse>('/api/dashboard/overview', {
      supplier_id: supplierId,
      start_date: startDate,
      end_date: endDate,
    }),

  getSalesOverTime: (
    supplierId: string,
    granularity: string,
    startDate?: string,
    endDate?: string
  ) =>
    get<SalesOverTimeResponse>('/api/dashboard/sales-over-time', {
      supplier_id: supplierId,
      granularity,
      start_date: startDate,
      end_date: endDate,
    }),

  getTopProducts: (
    supplierId: string,
    startDate?: string,
    endDate?: string,
    region?: string
  ) =>
    get<TopProductsResponse>('/api/dashboard/top-products', {
      supplier_id: supplierId,
      start_date: startDate,
      end_date: endDate,
      limit: 5,
      region,
    }),

  getRegions: (supplierId: string, startDate?: string, endDate?: string) =>
    get<RegionsResponse>('/api/dashboard/regions', {
      supplier_id: supplierId,
      start_date: startDate,
      end_date: endDate,
    }),

  getMarketShare: (
    supplierId: string,
    categoryName: string,
    startDate?: string,
    endDate?: string
  ) =>
    get<MarketShareResponse>('/api/dashboard/market-share', {
      supplier_id: supplierId,
      category_name: categoryName,
      start_date: startDate,
      end_date: endDate,
    }),

  getDecliningProducts: (supplierId: string, days: number) =>
    get<DecliningProductsResponse>('/api/dashboard/declining-products', {
      supplier_id: supplierId,
      days,
      limit: 5,
    }),

  chat: (req: ChatRequest): Promise<ChatResponse> =>
    fetch(`${BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    }).then(async res => {
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}))
        throw new Error(detail?.detail ?? `HTTP ${res.status}`)
      }
      return res.json() as Promise<ChatResponse>
    }),
}
