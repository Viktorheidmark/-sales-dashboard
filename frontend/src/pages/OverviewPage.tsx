import { useState, useEffect, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
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
import { PageHeader } from '../components/layout/PageHeader'
import { KpiCards } from '../components/sections/KpiCards'
import { SalesTrend } from '../components/sections/SalesTrend'
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

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-[0.16em] mb-3">{children}</p>
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

  return (
    <div className="space-y-8">
      <PageHeader
        title="Försäljningsöversikt"
        right={
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-0.5 bg-white border border-slate-200 rounded-lg p-1">
              {DATE_PRESETS.map(p => (
                <button
                  key={p.value}
                  onClick={() => setDatePreset(p.value)}
                  className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-colors ${
                    datePreset === p.value
                      ? 'bg-slate-900 text-white'
                      : 'text-slate-500 hover:text-slate-900 hover:bg-slate-50'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <button
              onClick={handleRefresh}
              disabled={anyLoading}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white border border-slate-200 text-slate-500 hover:text-slate-900 text-xs font-medium transition-colors disabled:opacity-40"
              aria-label="Uppdatera"
            >
              <span className={anyLoading ? 'animate-spin inline-block' : 'inline-block'}>↻</span>
              Uppdatera
            </button>
          </div>
        }
      />

      {/* KPIs */}
      <div>
        <SectionLabel>Nyckeltal</SectionLabel>
        <KpiCards
          data={overview.data}
          loading={overview.loading}
          error={overview.error}
          onRetry={handleRefresh}
          periodLabel={periodLabel}
        />
        {latestOrderDate && (
          <p className="mt-2.5 text-[11px] text-slate-400">
            Senast transaktionsdatum: {formatShortDate(latestOrderDate)}
          </p>
        )}
      </div>

      {/* Executive hero card — two-column stable grid */}
      {(worst || topRegion) && (
        <div className="bg-slate-900 rounded-xl overflow-hidden">
          <div className="grid grid-cols-1 sm:grid-cols-[13rem_1px_1fr]">

            {/* Left: primary signal */}
            <div className="pl-7 pr-9 py-7 flex flex-col gap-1">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-[0.18em] mb-2">
                Viktigaste signal
              </p>
              {worst && worstPct ? (
                <>
                  <p className="text-5xl font-bold text-red-400 tabular-nums leading-none">
                    −{worstPct}%
                  </p>
                  <p className="mt-2 text-[11px] text-slate-500 leading-snug">
                    Intäktsnedgång<br />vs. föregående period
                  </p>
                </>
              ) : topRegion ? (
                <>
                  <p className="text-5xl font-bold text-slate-200 tabular-nums leading-none">#1</p>
                  <p className="mt-2 text-[11px] text-slate-500 leading-snug">
                    Starkaste region
                  </p>
                </>
              ) : null}
              <Link
                to="/assistant"
                className="mt-auto pt-5 text-xs font-medium text-brand-400 hover:text-brand-300 transition-colors self-start"
              >
                Analysera →
              </Link>
            </div>

            {/* Vertical divider */}
            <div className="hidden sm:block bg-slate-800" />

            {/* Right: narrative context */}
            <div className="px-7 py-7 border-t border-slate-800 sm:border-t-0 flex flex-col gap-5">
              {worst && worstPct && (
                <div>
                  <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-[0.16em] mb-2">
                    Produkt i nedgång
                  </p>
                  <p className="text-sm font-semibold text-slate-100">{worst.product_name}</p>
                  <p className="mt-1.5 text-sm text-slate-400 leading-relaxed max-w-prose">
                    Omsättningen har fallit med {worstPct}% jämfört med föregående period.
                    Åtgärd rekommenderas om trenden håller i sig.
                  </p>
                </div>
              )}
              {topRegion && (
                <div className={worst ? 'border-t border-slate-800 pt-5' : ''}>
                  <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-[0.16em] mb-2">
                    Starkaste region
                  </p>
                  <p className="text-sm font-semibold text-slate-100">{topRegion.region}</p>
                  <p className="mt-1.5 text-sm text-slate-400 leading-relaxed">
                    Genererar mest omsättning under perioden och bör prioriteras i kommande kampanjplanering.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Sales trend */}
      <div>
        <SectionLabel>Försäljningsutveckling</SectionLabel>
        <SalesTrend
          data={trend.data}
          loading={trend.loading}
          error={trend.error}
          onRetry={handleRefresh}
        />
      </div>

      {/* Products & regions */}
      <div>
        <SectionLabel>Produkter och regioner</SectionLabel>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
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
      </div>

      {/* Market position & risks */}
      <div>
        <SectionLabel>Marknadsposition och risker</SectionLabel>
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
      </div>

      <p className="text-[11px] text-slate-300 pb-2">Syntetisk demodata · Solvigo Sales Intelligence</p>
    </div>
  )
}
