import type { DeepDiveDriver, DeepDivePayload } from '../../api/types'
import { formatCompactSEK } from '../../utils/compactCurrency'

function pctLabel(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(1).replace('.', ',')} %`
}

function deltaLabel(value: number): string {
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toLocaleString('sv-SE')}`
}

function DriverList({
  title,
  items,
  labelKey,
  compact = false,
}: {
  title: string
  items: DeepDiveDriver[]
  labelKey: 'product_name' | 'region'
  compact?: boolean
}) {
  if (!items.length) return null
  return (
    <div className={compact ? 'space-y-1' : 'space-y-1.5'}>
      <p className="text-[10px] font-semibold uppercase tracking-wide text-theme-muted">{title}</p>
      <ul className="space-y-1.5">
        {items.map((row, i) => {
          const label = String(row[labelKey] ?? '')
          const change = row.revenue_change
          const pct = row.revenue_change_pct
          const negative = change < 0
          return (
            <li key={`${label}-${i}`} className="flex items-baseline justify-between gap-3 text-xs">
              <span className="text-theme-body truncate min-w-0">{label}</span>
              <span className={`shrink-0 tabular-nums font-medium ${
                negative ? 'text-red-600 dark:text-red-400' : 'text-emerald-600 dark:text-emerald-400'
              }`}>
                {formatCompactSEK(change)}
                {pct != null && <span className="opacity-75 ml-1">({pctLabel(pct)})</span>}
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function PeriodSummary({ deepDive }: { deepDive: DeepDivePayload }) {
  const summary = deepDive.period_summary
  if (!summary) return null
  const positive = (summary.revenue_change_pct ?? 0) >= 0
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
      <div>
        <p className="text-[10px] uppercase tracking-wide text-theme-muted">Omsättning</p>
        <p className={`text-sm font-semibold tabular-nums mt-0.5 ${positive ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
          {formatCompactSEK(summary.revenue_change)}
        </p>
        <p className="text-[11px] text-theme-muted">{pctLabel(summary.revenue_change_pct)}</p>
      </div>
      <div>
        <p className="text-[10px] uppercase tracking-wide text-theme-muted">Ordrar</p>
        <p className="text-sm font-semibold tabular-nums text-theme-heading mt-0.5">
          {deltaLabel(summary.orders_change)}
        </p>
      </div>
      <div>
        <p className="text-[10px] uppercase tracking-wide text-theme-muted">Enheter</p>
        <p className="text-sm font-semibold tabular-nums text-theme-heading mt-0.5">
          {deltaLabel(summary.units_change)}
        </p>
      </div>
    </div>
  )
}

export function DeepDivePanel({ deepDive }: { deepDive: DeepDivePayload }) {
  if (deepDive.kind === 'revenue_development') {
    return (
      <div className="assistant-support-card space-y-3">
        <div className="flex items-baseline justify-between gap-3">
          <p className="text-xs font-semibold text-theme-heading">Vad drev förändringen?</p>
          <span className="text-[11px] text-theme-muted">Senaste {deepDive.comparison_days} dagarna</span>
        </div>
        {deepDive.relatively_stable && (
          <p className="text-[11px] text-theme-muted italic -mt-1">
            Försäljningen var relativt stabil under perioden.
          </p>
        )}
        <PeriodSummary deepDive={deepDive} />
        <div className="grid sm:grid-cols-2 gap-4 pt-2 border-t border-workspace-border/40">
          <DriverList title="Största ökningar" items={deepDive.top_gainers ?? []} labelKey="product_name" compact />
          <DriverList title="Största tapp" items={deepDive.top_losers ?? []} labelKey="product_name" compact />
        </div>
        {(deepDive.strongest_region || deepDive.weakest_region) && (
          <div className="grid sm:grid-cols-2 gap-4 pt-2 border-t border-workspace-border/40">
            {deepDive.strongest_region && (
              <DriverList title="Starkaste region" items={[deepDive.strongest_region]} labelKey="region" compact />
            )}
            {deepDive.weakest_region && (
              <DriverList title="Svagaste region" items={[deepDive.weakest_region]} labelKey="region" compact />
            )}
          </div>
        )}
      </div>
    )
  }

  if (deepDive.kind === 'product_decline') {
    const focus = deepDive.focus_product
    const decliningRegions = (focus?.top_regions ?? []).filter(r => (r.revenue_change ?? 0) < 0)
    const portfolio = (deepDive.portfolio_comparison ?? []).filter(
      (p, i) => i > 0 || (p.revenue_change ?? 0) < 0,
    )

    return (
      <div className="space-y-2.5">
        {decliningRegions.length > 0 && (
          <div className="assistant-support-card">
            <DriverList title="Var syns tappet?" items={decliningRegions} labelKey="region" compact />
          </div>
        )}
        {portfolio.length > 1 && (
          <div className="assistant-support-card">
            <DriverList title="Jämfört med övriga produkter" items={portfolio.slice(0, 4)} labelKey="product_name" compact />
          </div>
        )}
      </div>
    )
  }

  return null
}
