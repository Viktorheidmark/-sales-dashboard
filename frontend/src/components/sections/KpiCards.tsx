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
    <span className={`text-[11px] font-semibold tabular-nums ${positive ? 'text-emerald-600' : 'text-red-500'}`}>
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

function KpiCard({ label, value, delta, compLabel }: KpiCardProps) {
  const hasDelta = delta !== undefined && delta !== null
  return (
    <div className="bg-white rounded-xl border border-slate-100 px-5 py-5">
      <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-[0.12em] leading-none">{label}</p>
      <p className="mt-3 text-[1.625rem] font-bold text-slate-900 tabular-nums leading-none">{value}</p>
      <div className="mt-2 flex items-center gap-1.5 min-h-[1rem]">
        {hasDelta && (
          <>
            <Delta pct={delta} />
            <span className="text-[10px] text-slate-400">{compLabel}</span>
          </>
        )}
      </div>
    </div>
  )
}

export function KpiCards({ data, loading, error, onRetry, periodLabel }: KpiCardsProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => <CardSkeleton key={i} />)}
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="bg-white rounded-xl border border-slate-100 p-6">
        <ErrorState message={error ?? 'Kunde inte hämta data.'} onRetry={onRetry} />
      </div>
    )
  }

  const compLabel = `vs. föreg. ${periodLabel}`

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <KpiCard
        label="Omsättning"
        value={formatSEK(data.total_revenue)}
        delta={pctChange(data.total_revenue, data.prev_total_revenue)}
        compLabel={compLabel}
      />
      <KpiCard
        label="Beställningar"
        value={formatNumber(data.total_orders)}
        delta={pctChange(data.total_orders, data.prev_total_orders)}
        compLabel={compLabel}
      />
      <KpiCard
        label="Sålda enheter"
        value={formatNumber(data.total_units)}
        delta={pctChange(data.total_units, data.prev_total_units)}
        compLabel={compLabel}
      />
      <KpiCard
        label="Snitt ordervärde"
        value={formatSEK(data.average_order_value)}
        delta={pctChange(data.average_order_value, data.prev_average_order_value)}
        compLabel={compLabel}
      />
    </div>
  )
}
