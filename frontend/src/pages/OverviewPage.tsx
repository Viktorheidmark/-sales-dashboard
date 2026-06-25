import { useState, useEffect, useMemo } from 'react'
import { api } from '../api/client'
import type {
  AuthUser,
  OverviewResponse,
  SalesOverTimeResponse,
  TopProductsResponse,
  RegionsResponse,
  MarketShareResponse,
} from '../api/types'
import { OverviewHero } from '../components/sections/OverviewHero'
import { KpiCards } from '../components/sections/KpiCards'
import { SalesTrend } from '../components/sections/SalesTrend'
import { TopProducts } from '../components/sections/TopProducts'
import { RegionalSales } from '../components/sections/RegionalSales'
import { MarketPosition } from '../components/sections/MarketPosition'
import { presetToDates, defaultCategory, overviewPeriodContextLabel, type DatePreset } from '../utils/dateRange'

interface SectionState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

function initialState<T>(): SectionState<T> {
  return { data: null, loading: true, error: null }
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h2 className="overview-section-title">{children}</h2>
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

  const periodContextLabel = overviewPeriodContextLabel(datePreset)

  return (
    <div className="overview-page overview-content-stage space-y-6 pb-4">
      {/* Hero header */}
      <OverviewHero
        user={user}
        datePreset={datePreset}
        onDatePresetChange={setDatePreset}
        onRefresh={handleRefresh}
        anyLoading={anyLoading}
        latestOrderDate={overview.data?.latest_order_date}
        generatedAt={overview.data?.generated_at}
      />

      {/* KPI row */}
      <KpiCards
        data={overview.data}
        loading={overview.loading}
        error={overview.error}
        onRetry={handleRefresh}
        compact
      />

      {/* Trend chart */}
      <SalesTrend
        data={trend.data}
        loading={trend.loading}
        error={trend.error}
        onRetry={handleRefresh}
        featured
        periodContextLabel={periodContextLabel}
        chartHeight={280}
      />

      {/* Products, regions, and market position */}
      <section>
        <SectionHeading>Produkter och regioner</SectionHeading>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 lg:gap-5">
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
          <div className="md:col-span-2 xl:col-span-1">
            <MarketPosition
              data={marketShare.data}
              loading={marketShare.loading}
              error={marketShare.error}
              onRetry={handleRefresh}
              supplierCategory={supplierCategory}
              periodContextLabel={periodContextLabel}
            />
          </div>
        </div>
      </section>
    </div>
  )
}
