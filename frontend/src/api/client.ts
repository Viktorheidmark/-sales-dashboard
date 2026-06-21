import type {
  AuthUser,
  ChatRequest,
  ChatResponse,
  DecliningProductsResponse,
  MarketShareResponse,
  OverviewResponse,
  RegionsResponse,
  SalesOverTimeResponse,
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
  const res = await fetch(url.toString(), { credentials: 'include' })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail?.detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail?.detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  // --- Auth ---
  login: (email: string, password: string) =>
    post<AuthUser>('/api/auth/login', { email, password }),

  logout: () =>
    post<{ ok: boolean }>('/api/auth/logout', {}),

  me: () =>
    get<AuthUser>('/api/auth/me'),

  // --- Dashboard (supplier_id derived from session cookie) ---
  getOverview: (startDate?: string, endDate?: string) =>
    get<OverviewResponse>('/api/dashboard/overview', {
      start_date: startDate,
      end_date: endDate,
    }),

  getSalesOverTime: (granularity: string, startDate?: string, endDate?: string) =>
    get<SalesOverTimeResponse>('/api/dashboard/sales-over-time', {
      granularity,
      start_date: startDate,
      end_date: endDate,
    }),

  getTopProducts: (startDate?: string, endDate?: string, region?: string) =>
    get<TopProductsResponse>('/api/dashboard/top-products', {
      start_date: startDate,
      end_date: endDate,
      limit: 5,
      region,
    }),

  getRegions: (startDate?: string, endDate?: string) =>
    get<RegionsResponse>('/api/dashboard/regions', {
      start_date: startDate,
      end_date: endDate,
    }),

  getMarketShare: (categoryName: string, startDate?: string, endDate?: string) =>
    get<MarketShareResponse>('/api/dashboard/market-share', {
      category_name: categoryName,
      start_date: startDate,
      end_date: endDate,
    }),

  getDecliningProducts: (days: number) =>
    get<DecliningProductsResponse>('/api/dashboard/declining-products', {
      days,
      limit: 5,
    }),

  chat: (req: ChatRequest): Promise<ChatResponse> =>
    post<ChatResponse>('/api/chat', req),
}
