import { useState, useEffect, useMemo, type ReactNode } from 'react'
import { api } from '../api/client'
import type {
  AuthUser,
  OverviewResponse,
  SalesOverTimeResponse,
  TopProductsResponse,
  RegionsResponse,
  MarketShareResponse,
} from '../api/types'
import { KpiCards } from '../components/sections/KpiCards'
import { SalesTrend } from '../components/sections/SalesTrend'
import { TopProducts } from '../components/sections/TopProducts'
import { RegionalSales } from '../components/sections/RegionalSales'
import { MarketShare } from '../components/sections/MarketShare'
import { DATE_PRESETS, presetToDates, defaultCategory, overviewPeriodContextLabel, type DatePreset } from '../utils/dateRange'

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
    <h2 className="text-base font-semibold text-theme-heading tracking-tight mb-4">
      {children}
    </h2>
  )
}

interface OverviewPageProps {
  user: AuthUser
}

export function OverviewPage({ user }: OverviewPageProps) {
  const [datePreset, setDatePreset] = useState<DatePreset>('all')
  const [refreshTick, setRefreshTick] = useState(0)

  const supplierCategory = useMemo(
    () => defaultCategory(user.supplier_name),
    [user.supplier_name],
  )

  const [overview, setOverview] = useState<SectionState<OverviewResponse>>(initialState())
  const [trend, setTrend] = useState<SectionState<SalesOverTimeResponse>>(initialState())
  const [topProducts, setTopProducts] = useState<SectionState<TopProductsResponse>>(initialState())
  const [regions, setRegions] = useState<SectionState<RegionsResponse>>(initialState())
  const [marketShare, setMarketShare] = useState<SectionState<MarketShareResponse>>(initialState())

  const anyLoading =
    overview.loading || trend.loading || topProducts.loading ||
    regions.loading || marketShare.loading

  useEffect(() => {
    const { startDate, endDate, granularity } = presetToDates(datePreset)

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
    load(setTopProducts, () => api.getTopProducts(startDate, endDate))
    load(setRegions, () => api.getRegions(startDate, endDate))
    load(setMarketShare, () => api.getMarketShare(supplierCategory, startDate, endDate))
  }, [datePreset, supplierCategory, refreshTick])

  const handleRefresh = () => setRefreshTick(t => t + 1)

  const latestOrderDate = overview.data?.latest_order_date
  const generatedAt = overview.data?.generated_at
  const periodContextLabel = overviewPeriodContextLabel(datePreset)

  return (
    <div className="space-y-8 pb-2">
      {/* Zone 1 — Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold text-theme-heading tracking-tight">
            Försäljningsöversikt
          </h1>
          <p className="mt-1.5 text-sm leading-snug truncate">
            <span className="text-theme-body font-medium">{user.supplier_name}</span>
            <span className="text-theme-faint mx-1.5" aria-hidden>·</span>
            <span className="text-theme-muted">Leverantörsvy</span>
          </p>
          {latestOrderDate && (
            <p className="mt-1 text-xs text-theme-faint">
              Senast transaktionsdatum: {formatShortDate(latestOrderDate)}
            </p>
          )}
        </div>
        <div className="flex flex-col items-start sm:items-end gap-2 shrink-0">
          {generatedAt && (
            <p className="text-xs text-theme-muted">
              Senast uppdaterad: {formatShortDate(generatedAt.slice(0, 10))}
            </p>
          )}
          <div className="flex items-center gap-2">
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
      </div>

      {/* Zone 2 — KPI row */}
      <KpiCards
        data={overview.data}
        loading={overview.loading}
        error={overview.error}
        onRetry={handleRefresh}
        compact
      />

      {/* Försäljningstrend */}
      <SalesTrend
        data={trend.data}
        loading={trend.loading}
        error={trend.error}
        onRetry={handleRefresh}
        featured
        periodContextLabel={periodContextLabel}
        chartHeight={280}
      />

      {/* Zone 5 — Products and regions */}
      <section>
        <SectionHeading>Produkter och regioner</SectionHeading>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <TopProducts
            data={topProducts.data}
            loading={topProducts.loading}
            error={topProducts.error}
            onRetry={handleRefresh}
            compact
            showAssistantLink
            periodContextLabel={periodContextLabel}
          />
          <RegionalSales
            data={regions.data}
            loading={regions.loading}
            error={regions.error}
            onRetry={handleRefresh}
            compact
            showAssistantLink
            periodContextLabel={periodContextLabel}
          />
        </div>
      </section>

      {/* Marknadsandel */}
      <section>
        <SectionHeading>Marknadsandel</SectionHeading>
        <MarketShare
          data={marketShare.data}
          loading={marketShare.loading}
          error={marketShare.error}
          onRetry={handleRefresh}
          supplierCategory={supplierCategory}
          fullWidth
        />
      </section>
    </div>
  )
}
