import { useState, useEffect } from 'react'
import { api } from './api/client'
import type {
  SupplierItem,
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
import { TopProducts } from './components/sections/TopProducts'
import { RegionalSales } from './components/sections/RegionalSales'
import { MarketShare } from './components/sections/MarketShare'
import { DecliningProducts } from './components/sections/DecliningProducts'

// Map date preset to { startDate, endDate, granularity } for API calls
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
    case 'all':  return { startDate: undefined,     endDate: undefined, granularity: 'month', days: 180 }
  }
}

// Default category per supplier name
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
  // Suppliers
  const [suppliers, setSuppliers] = useState<SupplierItem[]>([])
  const [suppliersError, setSuppliersError] = useState<string | null>(null)
  const [selectedSupplierId, setSelectedSupplierId] = useState('')

  // Controls
  const [datePreset, setDatePreset] = useState<DatePreset>('90d')
  const [selectedRegion, setSelectedRegion] = useState('All regions')
  const [selectedCategory, setSelectedCategory] = useState('Coffee')
  const [refreshTick, setRefreshTick] = useState(0)

  // Section data
  const [overview, setOverview] = useState<SectionState<OverviewResponse>>(initialState())
  const [trend, setTrend] = useState<SectionState<SalesOverTimeResponse>>(initialState())
  const [topProducts, setTopProducts] = useState<SectionState<TopProductsResponse>>(initialState())
  const [regions, setRegions] = useState<SectionState<RegionsResponse>>(initialState())
  const [marketShare, setMarketShare] = useState<SectionState<MarketShareResponse>>(initialState())
  const [declining, setDeclining] = useState<SectionState<DecliningProductsResponse>>(initialState())

  // Derived
  const anyLoading =
    overview.loading || trend.loading || topProducts.loading ||
    regions.loading || marketShare.loading || declining.loading

  // Load suppliers once
  useEffect(() => {
    api.getSuppliers()
      .then(res => {
        setSuppliers(res.suppliers)
        // Default to Nordic Coffee AB
        const nordic = res.suppliers.find(s => s.name.includes('Nordic Coffee'))
        const first = res.suppliers[0]
        const chosen = nordic ?? first
        if (chosen) {
          setSelectedSupplierId(chosen.id)
          setSelectedCategory(defaultCategory(chosen.name))
        }
      })
      .catch(e => setSuppliersError(String(e.message ?? e)))
  }, [])

  // Reload dashboard whenever supplier, date preset, region, category, or refresh changes
  useEffect(() => {
    if (!selectedSupplierId) return

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

    load(setOverview, () => api.getOverview(selectedSupplierId, startDate, endDate))
    load(setTrend, () => api.getSalesOverTime(selectedSupplierId, granularity, startDate, endDate))
    load(setTopProducts, () => api.getTopProducts(selectedSupplierId, startDate, endDate, regionParam))
    load(setRegions, () => api.getRegions(selectedSupplierId, startDate, endDate))
    load(setMarketShare, () => api.getMarketShare(selectedSupplierId, selectedCategory, startDate, endDate))
    load(setDeclining, () => api.getDecliningProducts(selectedSupplierId, days))
  }, [selectedSupplierId, datePreset, selectedRegion, selectedCategory, refreshTick])

  const handleSupplierChange = (id: string) => {
    const supplier = suppliers.find(s => s.id === id)
    if (supplier) setSelectedCategory(defaultCategory(supplier.name))
    setSelectedRegion('All regions')
    setSelectedSupplierId(id)
  }

  const handleRefresh = () => setRefreshTick(t => t + 1)

  if (suppliersError) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-50">
        <div className="text-center">
          <p className="text-lg font-semibold text-zinc-700">Cannot reach API</p>
          <p className="text-sm text-zinc-400 mt-1">{suppliersError}</p>
          <p className="text-xs text-zinc-400 mt-3">
            Make sure the backend is running: <code className="bg-zinc-100 px-1 rounded">uvicorn app.main:app --reload</code>
          </p>
        </div>
      </div>
    )
  }

  if (!selectedSupplierId) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-50">
        <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-zinc-50">
      <Header
        suppliers={suppliers}
        selectedSupplierId={selectedSupplierId}
        onSupplierChange={handleSupplierChange}
        datePreset={datePreset}
        onDatePresetChange={setDatePreset}
        onRefresh={handleRefresh}
        loading={anyLoading}
      />

      <main className="max-w-screen-xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        {/* KPI cards */}
        <KpiCards
          data={overview.data}
          loading={overview.loading}
          error={overview.error}
          onRetry={handleRefresh}
        />

        {/* Sales trend */}
        <SalesTrend
          data={trend.data}
          loading={trend.loading}
          error={trend.error}
          onRetry={handleRefresh}
        />

        {/* Two-column: top products + regional */}
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

        {/* Two-column: market share + declining */}
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
      </main>

      <footer className="max-w-screen-xl mx-auto px-6 py-6 mt-4 border-t border-zinc-200">
        <p className="text-xs text-zinc-400">
          Solvigo Sales Intelligence · All data grounded via MCP analytics layer · No simulated or mock data
        </p>
      </footer>
    </div>
  )
}
