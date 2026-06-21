import type { OverviewResponse } from '../../api/types'
import { formatSEK, formatNumber } from '../../utils/format'
import { CardSkeleton } from '../ui/Skeleton'
import { ErrorState } from '../ui/ErrorState'
import { MetaFooter } from '../ui/MetaFooter'

interface KpiCardsProps {
  data: OverviewResponse | null
  loading: boolean
  error: string | null
  onRetry: () => void
}

function KpiCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-white rounded-xl border border-zinc-200 shadow-sm px-6 py-5">
      <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider">{label}</p>
      <p className="mt-1 text-2xl font-bold text-zinc-900 tabular-nums">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-zinc-400">{sub}</p>}
    </div>
  )
}

export function KpiCards({ data, loading, error, onRetry }: KpiCardsProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => <CardSkeleton key={i} />)}
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="bg-white rounded-xl border border-zinc-200 p-6">
        <ErrorState message={error ?? 'No data available'} onRetry={onRetry} />
      </div>
    )
  }

  const dateLabel = `${data.date_range.start} → ${data.date_range.end}`

  return (
    <div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Revenue"
          value={formatSEK(data.total_revenue)}
          sub={dateLabel}
        />
        <KpiCard
          label="Orders"
          value={formatNumber(data.total_orders)}
          sub={dateLabel}
        />
        <KpiCard
          label="Units sold"
          value={formatNumber(data.total_units)}
          sub={dateLabel}
        />
        <KpiCard
          label="Avg order value"
          value={formatSEK(data.average_order_value)}
          sub={dateLabel}
        />
      </div>
      <div className="mt-2 px-1">
        <MetaFooter source={data.source} generatedAt={data.generated_at} />
      </div>
    </div>
  )
}
