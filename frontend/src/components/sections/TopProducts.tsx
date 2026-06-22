import type { TopProductsResponse, RegionsResponse } from '../../api/types'
import { formatSEK, formatNumber } from '../../utils/format'
import { Card, CardHeader, CardBody } from '../ui/Card'
import { Skeleton } from '../ui/Skeleton'
import { ErrorState } from '../ui/ErrorState'

interface TopProductsProps {
  data: TopProductsResponse | null
  regionsData: RegionsResponse | null
  loading: boolean
  error: string | null
  onRetry: () => void
  selectedRegion: string
  onRegionChange: (r: string) => void
}

export function TopProducts({
  data, regionsData, loading, error, onRetry,
  selectedRegion, onRegionChange,
}: TopProductsProps) {
  const regionOptions = [
    { value: 'all', label: 'Alla regioner' },
    ...(regionsData?.regions.map(r => ({ value: r.region, label: r.region })) ?? []),
  ]

  const maxRevenue = data?.products[0]?.revenue ?? 1

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">Topprodukter</h2>
            <p className="text-xs text-slate-400 mt-0.5">Rankade efter omsättning</p>
          </div>
          <select
            value={selectedRegion}
            onChange={e => onRegionChange(e.target.value)}
            className="text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 text-slate-600 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent shrink-0"
          >
            {regionOptions.map(r => (
              <option key={r.value} value={r.value}>{r.label}</option>
            ))}
          </select>
        </div>
      </CardHeader>
      <CardBody>
        {loading ? (
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-11 w-full" />)}
          </div>
        ) : error || !data ? (
          <ErrorState message={error ?? 'Kunde inte hämta data.'} onRetry={onRetry} />
        ) : data.products.length === 0 ? (
          <p className="text-sm text-slate-400 text-center py-8">Inga produkter hittades för vald period</p>
        ) : (
          <div>
            {/* Column header */}
            <div className="grid grid-cols-[1.25rem_1fr_3.5rem_4.5rem] gap-x-3 mb-2 px-1">
              <span />
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">Produkt</span>
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide text-right">Enheter</span>
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide text-right">Omsättning</span>
            </div>
            {data.products.map((p, idx) => {
              const pct = ((p.revenue ?? 0) / maxRevenue) * 100
              const isTop = idx === 0
              return (
                <div
                  key={p.sku}
                  className={`grid grid-cols-[1.25rem_1fr_3.5rem_4.5rem] gap-x-3 items-center py-2.5 border-b border-slate-50 last:border-0 px-1 ${isTop ? 'rounded-lg bg-slate-50 -mx-1 px-2' : ''}`}
                >
                  <span className={`text-xs font-bold tabular-nums leading-none ${isTop ? 'text-brand-500' : 'text-slate-300'}`}>
                    {p.rank}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-800 truncate leading-snug">{p.product_name}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-[11px] text-slate-400">{p.sku}</span>
                      <div className="flex-1 h-px bg-slate-100 rounded-full overflow-hidden max-w-[4rem]">
                        <div
                          className={`h-full rounded-full ${isTop ? 'bg-brand-400' : 'bg-slate-300'}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  </div>
                  <span className="text-xs text-slate-500 tabular-nums text-right">{formatNumber(p.units)}</span>
                  <span className={`text-sm font-semibold tabular-nums text-right ${isTop ? 'text-slate-900' : 'text-slate-700'}`}>
                    {formatSEK(p.revenue)}
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </CardBody>
    </Card>
  )
}
