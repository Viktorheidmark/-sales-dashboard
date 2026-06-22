import type { TopProductsResponse, RegionsResponse } from '../../api/types'
import { formatSEK, formatNumber } from '../../utils/format'
import { Card, CardHeader, CardBody } from '../ui/Card'
import { Skeleton } from '../ui/Skeleton'
import { ErrorState } from '../ui/ErrorState'
import { MetaFooter } from '../ui/MetaFooter'

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
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <h2 className="text-sm font-semibold text-zinc-700">Topprodukter</h2>
          <select
            value={selectedRegion}
            onChange={e => onRegionChange(e.target.value)}
            className="text-xs border border-zinc-200 rounded-md px-2 py-1 text-zinc-600 bg-white focus:outline-none focus:ring-1 focus:ring-brand-500"
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
            {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
          </div>
        ) : error || !data ? (
          <ErrorState message={error ?? 'Kunde inte hämta data.'} onRetry={onRetry} />
        ) : data.products.length === 0 ? (
          <p className="text-sm text-zinc-400 text-center py-6">Inga produkter hittades för vald period</p>
        ) : (
          <div className="space-y-3">
            {data.products.map(p => {
              const pct = ((p.revenue ?? 0) / maxRevenue) * 100
              return (
                <div key={p.sku}>
                  <div className="flex items-center justify-between text-sm mb-1">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-xs font-semibold text-zinc-400 w-5 shrink-0">#{p.rank}</span>
                      <span className="font-medium text-zinc-800 truncate">{p.product_name}</span>
                      <span className="text-xs text-zinc-400 shrink-0 hidden sm:inline">{p.sku}</span>
                    </div>
                    <div className="flex items-center gap-3 shrink-0 ml-2">
                      <span className="text-xs text-zinc-400">{formatNumber(p.units)} enheter</span>
                      <span className="font-semibold text-zinc-900 tabular-nums">{formatSEK(p.revenue)}</span>
                    </div>
                  </div>
                  <div className="h-1.5 bg-zinc-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-brand-500 transition-all duration-500"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        )}
        {data && (
          <MetaFooter
            source={data.source}
            generatedAt={data.generated_at}
            rowCount={data.row_count}
          />
        )}
      </CardBody>
    </Card>
  )
}
