import { Link } from 'react-router-dom'
import type { TopProductsResponse } from '../../api/types'
import { formatSEK, formatNumber } from '../../utils/format'
import { Card, CardHeader, CardBody } from '../ui/Card'
import { Skeleton } from '../ui/Skeleton'
import { ErrorState } from '../ui/ErrorState'

const SKELETON_ROWS = 6

interface TopProductsProps {
  data: TopProductsResponse | null
  loading: boolean
  error: string | null
  onRetry: () => void
  compact?: boolean
  showAssistantLink?: boolean
  periodContextLabel?: string
}

export function TopProducts({
  data,
  loading,
  error,
  onRetry,
  compact = false,
  showAssistantLink = false,
  periodContextLabel,
}: TopProductsProps) {
  const products = data?.products ?? []
  const maxRevenue = products[0]?.revenue ?? 1

  return (
    <Card>
      <CardHeader>
        <div>
          <h2 className="text-sm font-semibold text-theme-heading">Topprodukter</h2>
          {periodContextLabel && (
            <p className="text-xs text-theme-muted mt-0.5">{periodContextLabel}</p>
          )}
        </div>
      </CardHeader>
      <CardBody>
        {loading ? (
          <div className="space-y-3">
            {[...Array(SKELETON_ROWS)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
          </div>
        ) : error || !data ? (
          <ErrorState message={error ?? 'Kunde inte hämta data.'} onRetry={onRetry} />
        ) : products.length === 0 ? (
          <p className="text-sm text-theme-muted text-center py-8">Inga produkter hittades för vald period</p>
        ) : (
          <div className="space-y-0">
            {products.map((p, idx) => {
              const pct = ((p.revenue ?? 0) / maxRevenue) * 100
              const isTop = idx === 0
              return (
                <div
                  key={p.sku}
                  className={`flex items-center gap-3 border-b border-workspace-border/50 last:border-0 ${
                    compact ? 'py-2' : 'py-2.5'
                  }`}
                >
                  <span
                    className="text-xs font-semibold tabular-nums w-4 shrink-0"
                    style={{ color: isTop ? 'var(--tenant-primary)' : 'var(--color-muted)' }}
                  >
                    {p.rank}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-theme-strong truncate leading-snug">{p.product_name}</p>
                    <div className="mt-1 h-1 bg-workspace-border/50 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${pct}%`,
                          backgroundColor: 'var(--tenant-chart-primary)',
                          opacity: isTop ? 0.85 : 0.4,
                        }}
                      />
                    </div>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className={`text-sm font-semibold tabular-nums ${isTop ? 'text-theme-heading' : 'text-theme-body'}`}>
                      {formatSEK(p.revenue)}
                    </p>
                    <p className="text-[11px] text-theme-muted tabular-nums">{formatNumber(p.units)} st</p>
                  </div>
                </div>
              )
            })}
          </div>
        )}
        {showAssistantLink && !loading && !error && (
          <Link
            to="/assistant"
            className="mt-4 inline-flex items-center gap-1 text-xs font-medium text-brand-600 dark:text-brand-400 hover:text-brand-700 dark:hover:text-brand-300 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50 rounded"
          >
            Öppna analysassistenten
            <span aria-hidden>→</span>
          </Link>
        )}
      </CardBody>
    </Card>
  )
}
