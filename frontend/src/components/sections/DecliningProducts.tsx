import type { DecliningProductsResponse } from '../../api/types'
import { formatSEK, formatPctChange } from '../../utils/format'
import { Card, CardHeader, CardBody } from '../ui/Card'
import { Skeleton } from '../ui/Skeleton'
import { ErrorState } from '../ui/ErrorState'
import { MetaFooter } from '../ui/MetaFooter'

interface DecliningProductsProps {
  data: DecliningProductsResponse | null
  loading: boolean
  error: string | null
  onRetry: () => void
}

const COLD_BREW_SKUS = new Set(['NCO-003', 'NCO-006'])

export function DecliningProducts({ data, loading, error, onRetry }: DecliningProductsProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-zinc-700">Declining products</h2>
          {data && (
            <span className="text-xs text-zinc-400">
              vs prior {data.comparison_days} days
            </span>
          )}
        </div>
      </CardHeader>
      <CardBody>
        {loading ? (
          <div className="space-y-3">
            {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-14 w-full" />)}
          </div>
        ) : error || !data ? (
          <ErrorState message={error ?? 'No data'} onRetry={onRetry} />
        ) : data.products.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 gap-2">
            <span className="text-2xl">✅</span>
            <p className="text-sm text-zinc-500">No products declining in this period</p>
          </div>
        ) : (
          <div className="space-y-2">
            {/* Period labels */}
            <div className="flex text-xs text-zinc-400 px-1 mb-3 gap-2">
              <span className="flex-1" />
              <span className="w-24 text-right">Prior</span>
              <span className="w-24 text-right">Latest</span>
              <span className="w-16 text-right">Change</span>
            </div>

            {data.products.map(p => {
              const isColdBrew = COLD_BREW_SKUS.has(p.sku)
              const changePct = p.revenue_change_pct

              return (
                <div
                  key={p.sku}
                  className={`rounded-lg px-3 py-3 border transition-colors ${
                    isColdBrew
                      ? 'bg-amber-50 border-amber-200'
                      : 'bg-zinc-50 border-zinc-100'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-zinc-400 w-5 shrink-0">#{p.rank}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm font-medium text-zinc-800 truncate">{p.product_name}</span>
                        {isColdBrew && (
                          <span className="shrink-0 text-xs bg-amber-100 text-amber-700 font-medium px-1.5 py-0.5 rounded">
                            Watch
                          </span>
                        )}
                      </div>
                      <span className="text-xs text-zinc-400">{p.sku}</span>
                    </div>
                    <span className="w-24 text-right text-xs text-zinc-500 tabular-nums">
                      {formatSEK(p.prior_period_revenue)}
                    </span>
                    <span className="w-24 text-right text-sm font-medium text-zinc-800 tabular-nums">
                      {formatSEK(p.latest_period_revenue)}
                    </span>
                    <span className={`w-16 text-right text-sm font-semibold tabular-nums ${
                      (changePct ?? 0) < -10 ? 'text-red-600' : 'text-orange-500'
                    }`}>
                      {formatPctChange(changePct)}
                    </span>
                  </div>

                  {/* Mini bar comparing prior vs latest */}
                  <div className="mt-2 flex gap-1 h-1.5">
                    <div
                      className="rounded-full bg-zinc-300"
                      style={{ width: '100%' }}
                    >
                      <div
                        className={`h-full rounded-full ${isColdBrew ? 'bg-amber-400' : 'bg-zinc-400'}`}
                        style={{
                          width: `${Math.max(1, (p.latest_period_revenue / p.prior_period_revenue) * 100)}%`,
                        }}
                      />
                    </div>
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
