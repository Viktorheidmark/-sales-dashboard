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
    <Card variant="dashboard">
      <CardHeader>
        <div>
          <h2 className="dashboard-panel-title">Topprodukter</h2>
          {periodContextLabel && (
            <p className="dashboard-panel-subtitle">{periodContextLabel}</p>
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
                  className={`dashboard-list-row flex items-center gap-3 ${
                    compact ? 'py-2' : 'py-2.5'
                  }`}
                >
                  <span
                    className={`dashboard-rank text-xs tabular-nums w-4 shrink-0 ${isTop ? 'dashboard-rank-top' : ''}`}
                  >
                    {p.rank}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm truncate leading-snug ${isTop ? 'dashboard-rank-name-top' : 'font-medium text-theme-strong'}`}>
                      {p.product_name}
                    </p>
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
          <div className="dashboard-card-footer-link">
            <Link
              to="/assistant"
              className="dashboard-inline-link inline-flex items-center gap-1 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50 rounded"
            >
              Öppna analysassistenten
              <span aria-hidden>→</span>
            </Link>
          </div>
        )}
      </CardBody>
    </Card>
  )
}
