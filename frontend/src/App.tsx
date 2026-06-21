import { useState, useEffect } from 'react'
import { api } from './api/client'
import type {
  AuthUser,
  OverviewResponse,
  SalesOverTimeResponse,
  TopProductsResponse,
  RegionsResponse,
  MarketShareResponse,
  DecliningProductsResponse,
} from './api/types'
import { daysAgo, today } from './utils/format'
import { Header, type DatePreset } from './components/layout/Header'
import { KpiCards } from './components/sections/KpiCards'
import { SalesTrend } from './components/sections/SalesTrend'
import { ChatPanel } from './components/sections/ChatPanel'
import { TopProducts } from './components/sections/TopProducts'
import { RegionalSales } from './components/sections/RegionalSales'
import { MarketShare } from './components/sections/MarketShare'
import { DecliningProducts } from './components/sections/DecliningProducts'
import { LoginPage } from './components/sections/LoginPage'

type AuthState = 'loading' | 'unauthenticated' | 'authenticated'

function presetToDates(preset: DatePreset): {
  startDate: string | undefined
  endDate: string | undefined
  granularity: string
  days: number
} {
  const end = today()
  switch (preset) {
    case '30d':  return { startDate: daysAgo(30),  endDate: end, granularity: 'day',   days: 30 }
    case '90d':  return { startDate: daysAgo(90),  endDate: end, granularity: 'week',  days: 90 }
    case '180d': return { startDate: daysAgo(180), endDate: end, granularity: 'month', days: 180 }
    case 'all':  return { startDate: undefined,    endDate: undefined, granularity: 'month', days: 180 }
  }
}

function defaultCategory(supplierName: string): string {
  if (supplierName.toLowerCase().includes('coffee')) return 'Coffee'
  if (supplierName.toLowerCase().includes('snack')) return 'Snacks'
  if (supplierName.toLowerCase().includes('home') || supplierName.toLowerCase().includes('clean')) return 'Household'
  return 'Coffee'
}

interface SectionState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

function initialState<T>(): SectionState<T> {
  return { data: null, loading: true, error: null }
}

export default function App() {
  const [authState, setAuthState] = useState<AuthState>('loading')
  const [user, setUser] = useState<AuthUser | null>(null)

  const [datePreset, setDatePreset] = useState<DatePreset>('90d')
  const [selectedRegion, setSelectedRegion] = useState('All regions')
  const [selectedCategory, setSelectedCategory] = useState('Coffee')
  const [refreshTick, setRefreshTick] = useState(0)

  const [overview, setOverview] = useState<SectionState<OverviewResponse>>(initialState())
  const [trend, setTrend] = useState<SectionState<SalesOverTimeResponse>>(initialState())
  const [topProducts, setTopProducts] = useState<SectionState<TopProductsResponse>>(initialState())
  const [regions, setRegions] = useState<SectionState<RegionsResponse>>(initialState())
  const [marketShare, setMarketShare] = useState<SectionState<MarketShareResponse>>(initialState())
  const [declining, setDeclining] = useState<SectionState<DecliningProductsResponse>>(initialState())

  const anyLoading =
    overview.loading || trend.loading || topProducts.loading ||
    regions.loading || marketShare.loading || declining.loading

  // Bootstrap session on mount
  useEffect(() => {
    api.me()
      .then(u => {
        setUser(u)
        setSelectedCategory(defaultCategory(u.supplier_name))
        setAuthState('authenticated')
      })
      .catch(() => setAuthState('unauthenticated'))
  }, [])

  // Load dashboard data whenever auth state or controls change
  useEffect(() => {
    if (authState !== 'authenticated') return

    const { startDate, endDate, granularity, days } = presetToDates(datePreset)
    const regionParam = selectedRegion === 'All regions' ? undefined : selectedRegion

    const load = <T,>(
      setter: React.Dispatch<React.SetStateAction<SectionState<T>>>,
      fetcher: () => Promise<T>
    ) => {
      setter(s => ({ ...s, loading: true, error: null }))
      fetcher()
        .then(data => setter({ data, loading: false, error: null }))
        .catch(e => setter({ data: null, loading: false, error: String(e.message ?? e) }))
    }

    load(setOverview, () => api.getOverview(startDate, endDate))
    load(setTrend, () => api.getSalesOverTime(granularity, startDate, endDate))
    load(setTopProducts, () => api.getTopProducts(startDate, endDate, regionParam))
    load(setRegions, () => api.getRegions(startDate, endDate))
    load(setMarketShare, () => api.getMarketShare(selectedCategory, startDate, endDate))
    load(setDeclining, () => api.getDecliningProducts(days))
  }, [authState, datePreset, selectedRegion, selectedCategory, refreshTick])

  const handleLogin = (u: AuthUser) => {
    setUser(u)
    setSelectedCategory(defaultCategory(u.supplier_name))
    setSelectedRegion('All regions')
    setDatePreset('90d')
    setAuthState('authenticated')
    setRefreshTick(t => t + 1)
  }

  const handleLogout = async () => {
    await api.logout().catch(() => {})
    setUser(null)
    setAuthState('unauthenticated')
  }

  const handleRefresh = () => setRefreshTick(t => t + 1)

  // Loading state (checking session)
  if (authState === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-50">
        <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  // Unauthenticated
  if (authState === 'unauthenticated') {
    return <LoginPage onLogin={handleLogin} />
  }

  // Authenticated dashboard
  return (
    <div className="min-h-screen bg-zinc-50">
      <Header
        supplierName={user?.supplier_name ?? ''}
        datePreset={datePreset}
        onDatePresetChange={setDatePreset}
        onRefresh={handleRefresh}
        onLogout={handleLogout}
        loading={anyLoading}
      />

      <main className="max-w-screen-xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        <KpiCards
          data={overview.data}
          loading={overview.loading}
          error={overview.error}
          onRetry={handleRefresh}
        />

        <SalesTrend
          data={trend.data}
          loading={trend.loading}
          error={trend.error}
          onRetry={handleRefresh}
        />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <TopProducts
            data={topProducts.data}
            regionsData={regions.data}
            loading={topProducts.loading}
            error={topProducts.error}
            onRetry={handleRefresh}
            selectedRegion={selectedRegion}
            onRegionChange={setSelectedRegion}
          />
          <RegionalSales
            data={regions.data}
            loading={regions.loading}
            error={regions.error}
            onRetry={handleRefresh}
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <MarketShare
            data={marketShare.data}
            loading={marketShare.loading}
            error={marketShare.error}
            onRetry={handleRefresh}
            selectedCategory={selectedCategory}
            onCategoryChange={setSelectedCategory}
          />
          <DecliningProducts
            data={declining.data}
            loading={declining.loading}
            error={declining.error}
            onRetry={handleRefresh}
          />
        </div>

        <ChatPanel
          supplierName={user?.supplier_name}
          startDate={presetToDates(datePreset).startDate}
          endDate={presetToDates(datePreset).endDate}
        />
      </main>

      <footer className="max-w-screen-xl mx-auto px-6 py-6 mt-4 border-t border-zinc-200">
        <p className="text-xs text-zinc-400">
          Solvigo Sales Intelligence · All data grounded via MCP analytics layer · No simulated or mock data
        </p>
      </footer>
    </div>
  )
}
