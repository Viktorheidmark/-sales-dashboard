import type { OverviewResponse } from '../../api/types'
import { formatSEK, formatNumber } from '../../utils/format'
import { CardSkeleton } from '../ui/Skeleton'
import { ErrorState } from '../ui/ErrorState'

interface KpiCardsProps {
  data: OverviewResponse | null
  loading: boolean
  error: string | null
  onRetry: () => void
  compact?: boolean
}

const KPI_ITEMS = [
  { key: 'revenue', label: 'Omsättning' },
  { key: 'orders', label: 'Beställningar' },
  { key: 'units', label: 'Sålda enheter' },
] as const

function KpiCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="dashboard-metric-card overview-kpi-card">
      <p className="dashboard-metric-label">{label}</p>
      <p className="dashboard-metric-value">{value}</p>
    </div>
  )
}

export function KpiCards({
  data,
  loading,
  error,
  onRetry,
  compact = false,
}: KpiCardsProps) {
  const gridClass = `overview-kpi-section grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 ${compact ? 'gap-3 sm:gap-4' : 'gap-4'}`

  if (loading) {
    return (
      <div className={gridClass}>
        {[...Array(3)].map((_, i) => (
          <div key={i} className={i === 2 ? 'md:col-span-2 lg:col-span-1' : undefined}>
            <CardSkeleton />
          </div>
        ))}
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="dashboard-panel p-5">
        <ErrorState message={error ?? 'Kunde inte hämta data.'} onRetry={onRetry} />
      </div>
    )
  }

  const values: Record<(typeof KPI_ITEMS)[number]['key'], string> = {
    revenue: formatSEK(data.total_revenue),
    orders: formatNumber(data.total_orders),
    units: formatNumber(data.total_units),
  }

  return (
    <div className={gridClass}>
      {KPI_ITEMS.map((item, i) => (
        <div
          key={item.key}
          className={i === 2 ? 'md:col-span-2 lg:col-span-1' : undefined}
        >
          <KpiCard label={item.label} value={values[item.key]} />
        </div>
      ))}
    </div>
  )
}
