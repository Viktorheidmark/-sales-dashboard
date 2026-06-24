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

interface KpiCardProps {
  label: string
  value: string
  secondaryLine?: string
}

function KpiCard({ label, value, secondaryLine, compact }: KpiCardProps & { compact?: boolean }) {
  return (
    <div className={`overview-kpi-card surface-elevated ${compact ? 'px-4 py-3.5' : 'px-5 py-5'}`}>
      <p className="text-xs font-medium text-theme-muted leading-none">{label}</p>
      <p className={`font-bold text-theme-heading tabular-nums leading-none ${compact ? 'mt-1.5 text-xl' : 'mt-3 text-[1.625rem]'}`}>
        {value}
      </p>
      {secondaryLine && (
        <p className={`text-xs text-theme-muted leading-snug ${compact ? 'mt-2' : 'mt-2.5'}`}>
          {secondaryLine}
        </p>
      )}
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
  if (loading) {
    return (
      <div className={`grid grid-cols-2 lg:grid-cols-4 ${compact ? 'gap-3' : 'gap-4'}`}>
        {[...Array(4)].map((_, i) => <CardSkeleton key={i} />)}
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="surface-card p-5">
        <ErrorState message={error ?? 'Kunde inte hämta data.'} onRetry={onRetry} />
      </div>
    )
  }

  return (
    <div className={`grid grid-cols-2 lg:grid-cols-4 ${compact ? 'gap-3' : 'gap-4'}`}>
      <KpiCard compact={compact} label="Omsättning" value={formatSEK(data.total_revenue)} />
      <KpiCard compact={compact} label="Beställningar" value={formatNumber(data.total_orders)} />
      <KpiCard compact={compact} label="Sålda enheter" value={formatNumber(data.total_units)} />
      <KpiCard
        compact={compact}
        label="Genomsnittligt ordervärde"
        value={formatSEK(data.average_order_value)}
      />
    </div>
  )
}
