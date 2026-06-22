import { useState, useEffect, type ReactNode } from 'react'
import { api } from '../api/client'
import type {
  AuthUser,
  OverviewResponse,
  SalesOverTimeResponse,
  TopProductsResponse,
  RegionsResponse,
  MarketShareResponse,
  DecliningProductsResponse,
} from '../api/types'
import { KpiCards } from '../components/sections/KpiCards'
import { SalesTrend } from '../components/sections/SalesTrend'
import { ExecutiveActionPanel } from '../components/sections/ExecutiveActionPanel'
import { TopProducts } from '../components/sections/TopProducts'
import { RegionalSales } from '../components/sections/RegionalSales'
import { MarketShare } from '../components/sections/MarketShare'
import { DecliningProducts } from '../components/sections/DecliningProducts'
import { DATE_PRESETS, presetToDates, defaultCategory, type DatePreset } from '../utils/dateRange'

interface SectionState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

function initialState<T>(): SectionState<T> {
  return { data: null, loading: true, error: null }
}

function formatShortDate(iso: string): string {
  return new Date(iso + 'T12:00:00').toLocaleDateString('sv-SE', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
}

function SectionHeading({ children }: { children: ReactNode }) {
  return (
    <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-[0.14em] mb-4">
      {children}
    </h2>
  )
}

interface OverviewPageProps {
  user: AuthUser
}

export function OverviewPage({ user }: OverviewPageProps) {
  const [datePreset, setDatePreset] = useState<DatePreset>('90d')
  const [selectedRegion, setSelectedRegion] = useState('all')
  const [selectedCategory, setSelectedCategory] = useState(() => defaultCategory(user.supplier_name))
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

  useEffect(() => {
    const { startDate, endDate, granularity, days } = presetToDates(datePreset)
    const regionParam = selectedRegion === 'all' ? undefined : selectedRegion

    const load = <T,>(
      setter: (s: SectionState<T> | ((prev: SectionState<T>) => SectionState<T>)) => void,
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
  }, [datePreset, selectedRegion, selectedCategory, refreshTick])

  const handleRefresh = () => setRefreshTick(t => t + 1)

  const worst = declining.data?.products[0]
  const topRegion = regions.data?.regions[0]
  const worstPct = worst?.revenue_change_pct != null
    ? Math.abs(worst.revenue_change_pct).toFixed(1)
    : null

  const latestOrderDate = overview.data?.latest_order_date
  const currentPreset = DATE_PRESETS.find(p => p.value === datePreset)
  const periodLabel = currentPreset?.label?.toLowerCase() ?? datePreset
  const periodDisplay = currentPreset?.label ?? datePreset

  return (
    <div className="space-y-7 pb-2">
      {/* Compact page header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-100 tracking-tight">
            Försäljningsöversikt
          </h1>
          {latestOrderDate && (
            <p className="mt-1 text-xs text-slate-500">
              Senast transaktionsdatum: {formatShortDate(latestOrderDate)}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <div className="segment-control">
            {DATE_PRESETS.map(p => (
              <button
                key={p.value}
                onClick={() => setDatePreset(p.value)}
                className={`segment-btn ${datePreset === p.value ? 'segment-btn-active' : ''}`}
              >
                {p.label}
              </button>
            ))}
          </div>
          <button
            onClick={handleRefresh}
            disabled={anyLoading}
            className="btn-ghost"
            aria-label="Uppdatera"
          >
            <span className={anyLoading ? 'animate-spin inline-block' : 'inline-block'}>↻</span>
            Uppdatera
          </button>
        </div>
      </div>

      {/* KPI row */}
      <KpiCards
        data={overview.data}
        loading={overview.loading}
        error={overview.error}
        onRetry={handleRefresh}
        periodLabel={periodLabel}
        compact
      />

      {/* Main decision area */}
      <div className="grid grid-cols-1 lg:grid-cols-10 gap-5 lg:gap-6 items-stretch">
        <div className="lg:col-span-7 min-w-0">
          <SalesTrend
            data={trend.data}
            loading={trend.loading}
            error={trend.error}
            onRetry={handleRefresh}
            featured
            periodLabel={periodDisplay}
          />
        </div>
        <div className="lg:col-span-3 min-w-0">
          <ExecutiveActionPanel
            worst={worst}
            worstPct={worstPct}
            topRegion={topRegion}
            marketShare={marketShare.data}
            selectedCategory={selectedCategory}
            decliningLoading={declining.loading}
            regionsLoading={regions.loading}
            marketShareLoading={marketShare.loading}
          />
        </div>
      </div>

      {/* Operational detail */}
      <section>
        <SectionHeading>Operativ detalj</SectionHeading>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <TopProducts
            data={topProducts.data}
            regionsData={regions.data}
            loading={topProducts.loading}
            error={topProducts.error}
            onRetry={handleRefresh}
            selectedRegion={selectedRegion}
            onRegionChange={setSelectedRegion}
            compact
          />
          <RegionalSales
            data={regions.data}
            loading={regions.loading}
            error={regions.error}
            onRetry={handleRefresh}
            compact
          />
        </div>
      </section>

      {/* Market position and risks */}
      <section>
        <SectionHeading>Marknadsposition och risker</SectionHeading>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
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
      </section>

      <p className="text-xs text-slate-600 pt-1">Syntetisk demodata · Solvigo Sales Intelligence</p>
    </div>
  )
}
