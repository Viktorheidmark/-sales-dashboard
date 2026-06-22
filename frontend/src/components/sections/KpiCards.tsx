import type { OverviewResponse } from '../../api/types'
import { formatSEK, formatNumber } from '../../utils/format'
import { CardSkeleton } from '../ui/Skeleton'
import { ErrorState } from '../ui/ErrorState'

interface KpiCardsProps {
  data: OverviewResponse | null
  loading: boolean
  error: string | null
  onRetry: () => void
  periodLabel: string
  compact?: boolean
}

function pctChange(current: number | null, prev: number | null): number | null {
  if (current == null || prev == null || prev === 0) return null
  return ((current - prev) / prev) * 100
}

function Delta({ pct }: { pct: number | null }) {
  if (pct == null) return null
  const positive = pct >= 0
  const sign = positive ? '+' : ''
  return (
    <span
      className={`text-xs font-semibold tabular-nums ${positive ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}
      aria-label={positive ? 'Positiv förändring' : 'Negativ förändring'}
    >
      {sign}{pct.toFixed(1).replace('.', ',')}%
    </span>
  )
}

interface KpiCardProps {
  label: string
  value: string
  delta?: number | null
  compLabel: string
}

function KpiCard({ label, value, delta, compLabel, compact }: KpiCardProps & { compact?: boolean }) {
  const hasDelta = delta !== undefined && delta !== null
  return (
    <div className={`surface-elevated ${compact ? 'px-4 py-3.5' : 'px-5 py-5'}`}>
      <p className="text-xs font-medium text-theme-muted leading-none">{label}</p>
      <p className={`font-bold text-theme-heading tabular-nums leading-none ${compact ? 'mt-1.5 text-xl' : 'mt-3 text-[1.625rem]'}`}>
        {value}
      </p>
      <div className={`flex items-center gap-1.5 min-h-[1rem] ${compact ? 'mt-1.5' : 'mt-2'}`}>
        {hasDelta && (
          <>
            <Delta pct={delta} />
            <span className="text-xs text-theme-muted">{compLabel}</span>
          </>
        )}
      </div>
    </div>
  )
}

export function KpiCards({ data, loading, error, onRetry, periodLabel, compact = false }: KpiCardsProps) {
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

  const compLabel = `vs. föreg. ${periodLabel}`

  return (
    <div className={`grid grid-cols-2 lg:grid-cols-4 ${compact ? 'gap-3' : 'gap-4'}`}>
      <KpiCard compact={compact} label="Omsättning" value={formatSEK(data.total_revenue)} delta={pctChange(data.total_revenue, data.prev_total_revenue)} compLabel={compLabel} />
      <KpiCard compact={compact} label="Beställningar" value={formatNumber(data.total_orders)} delta={pctChange(data.total_orders, data.prev_total_orders)} compLabel={compLabel} />
      <KpiCard compact={compact} label="Sålda enheter" value={formatNumber(data.total_units)} delta={pctChange(data.total_units, data.prev_total_units)} compLabel={compLabel} />
      <KpiCard compact={compact} label="Snitt ordervärde" value={formatSEK(data.average_order_value)} delta={pctChange(data.average_order_value, data.prev_average_order_value)} compLabel={compLabel} />
    </div>
  )
}
