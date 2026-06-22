import type { DecliningProductsResponse } from '../../api/types'
import { formatSEK, formatPctChange } from '../../utils/format'
import { Card, CardHeader, CardBody } from '../ui/Card'
import { Skeleton } from '../ui/Skeleton'
import { ErrorState } from '../ui/ErrorState'

interface DecliningProductsProps {
  data: DecliningProductsResponse | null
  loading: boolean
  error: string | null
  onRetry: () => void
}

const WATCH_SKUS = new Set(['ARLA-004'])

export function DecliningProducts({ data, loading, error, onRetry }: DecliningProductsProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">Produkter att bevaka</h2>
            <p className="text-xs text-slate-500 mt-0.5">Nedgång mot föregående period</p>
          </div>
          {data && (
            <span className="text-xs font-medium text-slate-400">
              {data.comparison_days} dagar
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
          <ErrorState message={error ?? 'Kunde inte hämta data.'} onRetry={onRetry} />
        ) : data.products.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 gap-2">
            <div className="w-8 h-8 rounded-full bg-emerald-50 border border-emerald-100 flex items-center justify-center">
              <svg className="w-4 h-4 text-emerald-500" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <p className="text-sm font-medium text-slate-700">Inga produkter i nedgång</p>
            <p className="text-xs text-slate-400">Alla produkter håller sig stabila</p>
          </div>
        ) : (
          <div className="space-y-1.5">
            {data.products.map((p, idx) => {
              const isFlagged = WATCH_SKUS.has(p.sku)
              const changePct = p.revenue_change_pct
              const severe = (changePct ?? 0) < -15

              return (
                <div
                  key={p.sku}
                  className={`rounded-lg px-3 py-2.5 border ${
                    isFlagged
                      ? 'bg-amber-50/80 border-amber-100'
                      : severe
                        ? 'bg-red-50/80 border-red-100'
                        : 'bg-slate-50/80 border-slate-100'
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <span className={`text-xs font-semibold mt-0.5 w-4 shrink-0 ${idx === 0 ? 'text-red-500' : 'text-slate-400'}`}>
                      {p.rank}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-sm font-medium text-slate-800 truncate">{p.product_name}</span>
                        {isFlagged && (
                          <span className="shrink-0 text-[10px] font-medium bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded">
                            Bevakning
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                        <span className="text-xs text-slate-400">{p.sku}</span>
                        <span className="text-xs text-slate-500">Föreg: {formatSEK(p.prior_period_revenue)}</span>
                        <span className="text-xs text-slate-600">Nu: {formatSEK(p.latest_period_revenue)}</span>
                      </div>
                    </div>
                    <span className={`text-sm font-semibold tabular-nums shrink-0 ${
                      severe ? 'text-red-600' : 'text-orange-600'
                    }`}>
                      {formatPctChange(changePct)}
                    </span>
                  </div>

                  <div className="mt-2 ml-6 h-0.5 bg-white rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${isFlagged ? 'bg-amber-400' : severe ? 'bg-red-400' : 'bg-slate-400'}`}
                      style={{
                        width: `${Math.max(2, Math.min(100, (p.latest_period_revenue / p.prior_period_revenue) * 100))}%`,
                      }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </CardBody>
    </Card>
  )
}
