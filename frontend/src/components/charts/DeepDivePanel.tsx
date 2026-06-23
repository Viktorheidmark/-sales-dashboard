import type { DeepDiveDriver, DeepDivePayload } from '../../api/types'
import { formatCompactSEK } from '../../utils/compactCurrency'

function pctLabel(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(1)} %`
}

function deltaLabel(value: number): string {
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toLocaleString('sv-SE')}`
}

function DriverList({
  title,
  items,
  labelKey,
}: {
  title: string
  items: DeepDiveDriver[]
  labelKey: 'product_name' | 'region'
}) {
  if (!items.length) return null
  return (
    <div className="space-y-1.5">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-theme-muted">{title}</p>
      <ul className="space-y-1">
        {items.map((row, i) => {
          const label = String(row[labelKey] ?? '')
          const change = row.revenue_change
          const pct = row.revenue_change_pct
          const positive = change >= 0
          return (
            <li key={`${label}-${i}`} className="flex items-baseline justify-between gap-3 text-xs">
              <span className="text-theme-body truncate">{label}</span>
              <span className={`shrink-0 tabular-nums font-medium ${positive ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
                {formatCompactSEK(change)}
                {pct != null && <span className="opacity-70 ml-1">({pctLabel(pct)})</span>}
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
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      <div>
        <p className="text-[10px] uppercase tracking-widest text-theme-muted">Omsättning</p>
        <p className={`text-sm font-semibold tabular-nums ${positive ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
          {formatCompactSEK(summary.revenue_change)}
        </p>
        <p className="text-[11px] text-theme-muted">{pctLabel(summary.revenue_change_pct)}</p>
      </div>
      <div>
        <p className="text-[10px] uppercase tracking-widest text-theme-muted">Ordrar</p>
        <p className="text-sm font-semibold tabular-nums text-theme-heading">
          {deltaLabel(summary.orders_change)}
        </p>
      </div>
      <div>
        <p className="text-[10px] uppercase tracking-widest text-theme-muted">Enheter</p>
        <p className="text-sm font-semibold tabular-nums text-theme-heading">
          {deltaLabel(summary.units_change)}
        </p>
      </div>
      <div>
        <p className="text-[10px] uppercase tracking-widest text-theme-muted">Perioder</p>
        <p className="text-[11px] text-theme-body leading-snug">
          {formatCompactSEK(summary.prior.total_revenue)} → {formatCompactSEK(summary.current.total_revenue)}
        </p>
      </div>
    </div>
  )
}

export function DeepDivePanel({ deepDive }: { deepDive: DeepDivePayload }) {
  if (deepDive.kind === 'revenue_development') {
    return (
      <div className="rounded-lg border border-workspace-border bg-workspace-surface px-4 py-3 space-y-4">
        <div className="flex items-baseline justify-between gap-3">
          <p className="text-xs font-semibold text-theme-heading">
            Vad drev förändringen?
          </p>
          <span className="text-[11px] text-theme-muted">Senaste {deepDive.comparison_days} dagarna</span>
        </div>
        {deepDive.relatively_stable && (
          <p className="text-[11px] text-theme-muted italic -mt-2">
            Försäljningen var relativt stabil under perioden.
          </p>
        )}
        <PeriodSummary deepDive={deepDive} />
        <div className="grid sm:grid-cols-2 gap-4 pt-1 border-t border-workspace-border/50">
          <DriverList title="Största ökningar" items={deepDive.top_gainers ?? []} labelKey="product_name" />
          <DriverList title="Största tapp" items={deepDive.top_losers ?? []} labelKey="product_name" />
        </div>
        {(deepDive.strongest_region || deepDive.weakest_region) && (
          <div className="grid sm:grid-cols-2 gap-4 pt-1 border-t border-workspace-border/50">
            {deepDive.strongest_region && (
              <DriverList title="Starkaste region" items={[deepDive.strongest_region]} labelKey="region" />
            )}
            {deepDive.weakest_region && (
              <DriverList title="Svagaste region" items={[deepDive.weakest_region]} labelKey="region" />
            )}
          </div>
        )}
      </div>
    )
  }

  if (deepDive.kind === 'product_decline') {
    const focus = deepDive.focus_product
    return (
      <div className="rounded-lg border border-workspace-border bg-workspace-surface px-4 py-3 space-y-4">
        {focus?.top_regions && focus.top_regions.length > 0 && (
          <div>
            <DriverList title="Var syns tappet?" items={focus.top_regions} labelKey="region" />
          </div>
        )}
        {(deepDive.portfolio_comparison?.length ?? 0) > 1 && (
          <div className="pt-1 border-t border-workspace-border/50">
            <DriverList title="Jämfört med övriga produkter" items={deepDive.portfolio_comparison ?? []} labelKey="product_name" />
          </div>
        )}
      </div>
    )
  }

  return null
}
