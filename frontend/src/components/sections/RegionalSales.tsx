import { Link } from 'react-router-dom'
import type { RegionsResponse } from '../../api/types'
import { formatSEK, formatNumber } from '../../utils/format'
import { Card, CardHeader, CardBody } from '../ui/Card'
import { Skeleton } from '../ui/Skeleton'
import { ErrorState } from '../ui/ErrorState'

const SKELETON_ROWS = 8

interface RegionalSalesProps {
  data: RegionsResponse | null
  loading: boolean
  error: string | null
  onRetry: () => void
  compact?: boolean
  showAssistantLink?: boolean
  periodContextLabel?: string
}

export function RegionalSales({
  data,
  loading,
  error,
  onRetry,
  compact = false,
  showAssistantLink = false,
  periodContextLabel,
}: RegionalSalesProps) {
  const regions = data?.regions ?? []
  const maxRev = regions[0]?.revenue ?? 1

  if (loading) {
    return (
      <Card variant="dashboard">
        <CardHeader>
          <h2 className="dashboard-panel-title">Försäljning per region</h2>
        </CardHeader>
        <CardBody>
          <div className="space-y-3">
            {[...Array(SKELETON_ROWS)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
          </div>
        </CardBody>
      </Card>
    )
  }

  if (error || !data) {
    return (
      <Card variant="dashboard">
        <CardHeader><h2 className="dashboard-panel-title">Försäljning per region</h2></CardHeader>
        <CardBody><ErrorState message={error ?? 'Kunde inte hämta data.'} onRetry={onRetry} /></CardBody>
      </Card>
    )
  }

  return (
    <Card variant="dashboard">
      <CardHeader>
        <div>
          <h2 className="dashboard-panel-title">Försäljning per region</h2>
          {periodContextLabel && (
            <p className="dashboard-panel-subtitle">{periodContextLabel}</p>
          )}
        </div>
      </CardHeader>
      <CardBody>
        {regions.length === 0 ? (
          <p className="text-sm text-theme-muted text-center py-8">Inga regionala försäljningsdata för vald period</p>
        ) : (
          <div className="space-y-0">
            {regions.map((r, i) => {
              const isTop = i === 0
              return (
              <div
                key={r.region}
                className={`dashboard-list-row flex items-center gap-3 ${
                  compact ? 'py-2' : 'py-2.5'
                }`}
              >
                <span
                  className={`dashboard-rank text-xs tabular-nums w-4 shrink-0 ${isTop ? 'dashboard-rank-top' : ''}`}
                >
                  {i + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <p className={`text-sm truncate ${isTop ? 'dashboard-rank-name-top' : 'font-medium text-theme-strong'}`}>{r.region}</p>
                  <div className="mt-1 h-1 bg-workspace-border/50 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${maxRev > 0 ? ((r.revenue ?? 0) / maxRev) * 100 : 0}%`,
                        backgroundColor: 'var(--tenant-chart-primary)',
                        opacity: isTop ? 0.85 : 0.4,
                      }}
                    />
                  </div>
                </div>
                <div className="shrink-0 text-right">
                  <p className={`text-sm tabular-nums ${isTop ? 'font-semibold text-theme-heading' : 'font-semibold text-theme-body'}`}>{formatSEK(r.revenue)}</p>
                  <p className="text-[11px] text-theme-muted tabular-nums">{formatNumber(r.orders)} ordrar</p>
                </div>
              </div>
            )})}
          </div>
        )}
        {showAssistantLink && (
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
