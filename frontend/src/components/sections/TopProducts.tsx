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
  compact?: boolean
}

export function TopProducts({
  data, regionsData, loading, error, onRetry,
  selectedRegion, onRegionChange, compact = false,
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
            <h2 className="text-sm font-semibold text-theme-heading">Topprodukter</h2>
            <p className="text-xs text-theme-muted mt-0.5">Rankade efter omsättning</p>
          </div>
          <select
            value={selectedRegion}
            onChange={e => onRegionChange(e.target.value)}
            className="input-select shrink-0"
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
          <p className="text-sm text-theme-muted text-center py-8">Inga produkter hittades för vald period</p>
        ) : (
          <div>
            <div className={`grid grid-cols-[1.25rem_1fr_3.5rem_4.5rem] gap-x-3 mb-1.5 px-0.5 ${compact ? '' : 'mb-2 px-1'}`}>
              <span />
              <span className="text-xs font-medium text-theme-muted">Produkt</span>
              <span className="text-xs font-medium text-theme-muted text-right">Enheter</span>
              <span className="text-xs font-medium text-theme-muted text-right">Omsättning</span>
            </div>
            {data.products.map((p, idx) => {
              const pct = ((p.revenue ?? 0) / maxRevenue) * 100
              const isTop = idx === 0
              return (
                <div
                  key={p.sku}
                  className={`grid grid-cols-[1.25rem_1fr_3.5rem_4.5rem] gap-x-3 items-center border-b border-workspace-border/50 last:border-0 ${
                    compact ? 'py-2' : 'py-2.5 px-1'
                  } ${isTop && !compact ? 'rounded-lg bg-workspace-muted/80 -mx-1 px-2' : ''}`}
                >
                  <span className={`text-xs font-semibold tabular-nums leading-none ${isTop ? 'text-brand-600 dark:text-brand-400' : 'text-theme-muted'}`}>
                    {p.rank}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-theme-strong truncate leading-snug">{p.product_name}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs text-theme-muted">{p.sku}</span>
                      <div className="flex-1 h-0.5 bg-workspace-border/60 rounded-full overflow-hidden max-w-[3.5rem]">
                        <div
                          className={`h-full rounded-full ${isTop ? 'bg-brand-500' : 'bg-workspace-border'}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  </div>
                  <span className="text-xs text-theme-muted tabular-nums text-right">{formatNumber(p.units)}</span>
                  <span className={`text-sm font-semibold tabular-nums text-right ${isTop ? 'text-theme-heading' : 'text-theme-body'}`}>
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
