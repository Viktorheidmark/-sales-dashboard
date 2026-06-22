import type {
  AuthUser,
  ChatRequest,
  ChatResponse,
  DecliningProductsResponse,
  InsightDetail,
  InsightSummary,
  MarketShareResponse,
  OverviewResponse,
  RegionsResponse,
  SalesOverTimeResponse,
  SaveInsightRequest,
  SaveInsightResponse,
  TopProductsResponse,
} from './types'

const BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

function handleHttpError(status: number): never {
  if (status === 401) {
    window.dispatchEvent(new CustomEvent('auth:expired'))
    throw new Error('Sessionen har gått ut. Logga in igen.')
  }
  throw new Error(`HTTP ${status}`)
}

async function get<T>(path: string, params: Record<string, string | number | undefined> = {}): Promise<T> {
  const url = new URL(`${BASE}${path}`)
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') {
      url.searchParams.set(k, String(v))
    }
  }
  const res = await fetch(url.toString(), { credentials: 'include' })
  if (!res.ok) {
    if (res.status === 401) handleHttpError(res.status)
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
    if (res.status === 401) handleHttpError(res.status)
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail?.detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

async function del(path: string): Promise<void> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'DELETE',
    credentials: 'include',
  })
  if (!res.ok) {
    if (res.status === 401) handleHttpError(res.status)
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail?.detail ?? `HTTP ${res.status}`)
  }
}

async function getBlob(path: string): Promise<Blob> {
  const res = await fetch(`${BASE}${path}`, { credentials: 'include' })
  if (!res.ok) {
    if (res.status === 401) handleHttpError(res.status)
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail?.detail ?? `HTTP ${res.status}`)
  }
  return res.blob()
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

  // --- Insights (supplier_id always derived from session cookie) ---
  saveInsight: (req: SaveInsightRequest): Promise<SaveInsightResponse> =>
    post<SaveInsightResponse>('/api/insights', req),

  listInsights: (limit = 20): Promise<InsightSummary[]> =>
    get<InsightSummary[]>('/api/insights', { limit }),

  getInsight: (id: string): Promise<InsightDetail> =>
    get<InsightDetail>(`/api/insights/${id}`),

  deleteInsight: (id: string): Promise<void> =>
    del(`/api/insights/${id}`),

  exportInsightPdf: (id: string): Promise<Blob> =>
    getBlob(`/api/insights/${id}/export.pdf`),
}
