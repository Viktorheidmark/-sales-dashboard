import type { DecliningProductsResponse } from '../../api/types'
import { formatPctChange } from '../../utils/format'
import { Card, CardHeader, CardBody } from '../ui/Card'
import { Skeleton } from '../ui/Skeleton'
import { ErrorState } from '../ui/ErrorState'

const MAX_ITEMS = 3

interface DecliningProductsProps {
  data: DecliningProductsResponse | null
  loading: boolean
  error: string | null
  onRetry: () => void
}

export function DecliningProducts({ data, loading, error, onRetry }: DecliningProductsProps) {
  const products = (data?.products ?? []).slice(0, MAX_ITEMS)

  return (
    <Card>
      <CardHeader>
        <div>
          <h2 className="text-sm font-semibold text-theme-heading">Produkter att bevaka</h2>
          <p className="text-xs text-theme-muted mt-0.5">Störst nedgång mot föregående period</p>
        </div>
      </CardHeader>
      <CardBody>
        {loading ? (
          <div className="space-y-2">
            {[...Array(MAX_ITEMS)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
          </div>
        ) : error || !data ? (
          <ErrorState message={error ?? 'Kunde inte hämta data.'} onRetry={onRetry} />
        ) : products.length === 0 ? (
          <p className="text-sm text-theme-muted py-6 text-center">Inga produkter i nedgång</p>
        ) : (
          <div className="space-y-2">
            {products.map((p, idx) => {
              const changePct = p.revenue_change_pct
              const isPrimary = idx === 0
              const severe = (changePct ?? 0) < -15

              return (
                <div
                  key={p.sku}
                  className={`rounded-lg px-3 py-2.5 ${
                    isPrimary
                      ? 'bg-red-500/[0.06] border border-red-500/15'
                      : 'bg-workspace-muted/40 border border-workspace-border/50'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className={`text-sm font-medium leading-snug truncate ${isPrimary ? 'text-theme-heading' : 'text-theme-strong'}`}>
                        {p.product_name}
                      </p>
                    </div>
                    <span
                      className={`text-sm font-semibold tabular-nums shrink-0 ${
                        severe || isPrimary ? 'text-red-600 dark:text-red-400' : 'text-orange-500 dark:text-orange-400'
                      }`}
                    >
                      {formatPctChange(changePct)}
                    </span>
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
