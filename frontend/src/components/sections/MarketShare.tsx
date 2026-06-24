import { Link } from 'react-router-dom'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import type { MarketShareResponse } from '../../api/types'
import { formatSEK } from '../../utils/format'
import { useChartTheme } from '../../utils/chartTheme'
import { Card, CardHeader, CardBody } from '../ui/Card'
import { Skeleton } from '../ui/Skeleton'
import { ErrorState } from '../ui/ErrorState'

interface MarketShareProps {
  data: MarketShareResponse | null
  loading: boolean
  error: string | null
  onRetry: () => void
  supplierCategory: string
  fullWidth?: boolean
}

function formatSharePct(value: number): string {
  return `${value.toLocaleString('sv-SE', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} %`
}

function marketShareAssistantPrompt(category: string): string {
  return `Hur stor är vår marknadsandel inom ${category}?`
}

function MetricBlock({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-theme-muted">{label}</p>
      <p className="mt-1 text-lg font-semibold text-theme-heading tabular-nums leading-tight">{value}</p>
    </div>
  )
}

export function MarketShare({
  data,
  loading,
  error,
  onRetry,
  supplierCategory,
  fullWidth = false,
}: MarketShareProps) {
  const { chart, chartTooltipStyle } = useChartTheme()

  const pieData = data
    ? [
        { name: 'Vår andel', value: data.supplier_revenue, color: chart.barPrimary },
        { name: 'Konkurrenter (aggregat)', value: data.competitor_aggregate_revenue ?? 0, color: chart.pieMuted },
      ]
    : []

  const remainingSharePct = data
    ? Math.max(0, 100 - data.market_share_pct)
    : null

  return (
    <Card>
      <CardHeader>
        <div>
          <h2 className="text-sm font-semibold text-theme-heading">Marknadsandel</h2>
          <p className="text-xs text-theme-muted mt-0.5">inom {supplierCategory}</p>
        </div>
      </CardHeader>
      <CardBody>
        {loading ? (
          <div className={fullWidth ? 'grid grid-cols-1 md:grid-cols-3 gap-8' : 'space-y-3'}>
            <div className="flex justify-center md:justify-start">
              <Skeleton className="w-36 h-36 rounded-full" />
            </div>
            <div className="space-y-4">
              <Skeleton className="h-12 w-40" />
              <Skeleton className="h-12 w-40" />
            </div>
            <div className="space-y-3">
              <Skeleton className="h-12 w-32" />
              <Skeleton className="h-4 w-48" />
            </div>
          </div>
        ) : error || !data ? (
          <ErrorState message={error ?? 'Kunde inte hämta data.'} onRetry={onRetry} />
        ) : fullWidth ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-10 items-center">
            <div className="flex flex-col items-center md:items-start">
              <ResponsiveContainer width={132} height={132}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={42}
                    outerRadius={62}
                    dataKey="value"
                    startAngle={90}
                    endAngle={-270}
                    strokeWidth={0}
                  >
                    {pieData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: number) => formatSEK(v)} contentStyle={chartTooltipStyle} />
                </PieChart>
              </ResponsiveContainer>
              <p className="-mt-1 text-2xl font-bold text-theme-heading tabular-nums leading-none">
                {formatSharePct(data.market_share_pct)}
              </p>
              <p className="text-xs text-theme-muted mt-1">Vår andel</p>
            </div>

            <div className="space-y-5 md:border-x md:border-workspace-border/50 md:px-8">
              <MetricBlock label="Vår omsättning" value={formatSEK(data.supplier_revenue)} />
              <MetricBlock label="Kategoritotal" value={formatSEK(data.category_total_revenue)} />
            </div>

            <div className="space-y-3 md:pl-2">
              <MetricBlock
                label="Övriga aktörer"
                value={remainingSharePct != null ? formatSharePct(remainingSharePct) : '—'}
              />
              <p className="text-[11px] text-theme-faint leading-snug">
                Konkurrentdata visas aggregerat
              </p>
              <Link
                to="/assistant"
                state={{ initialPrompt: marketShareAssistantPrompt(supplierCategory) }}
                className="inline-flex items-center gap-1 text-xs font-medium text-brand-600 dark:text-brand-400 hover:text-brand-700 dark:hover:text-brand-300 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50 rounded"
              >
                Analysera marknadsandelen
                <span aria-hidden>→</span>
              </Link>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-4">
            <div className="shrink-0 flex flex-col items-center">
              <ResponsiveContainer width={118} height={118}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={38}
                    outerRadius={56}
                    dataKey="value"
                    startAngle={90}
                    endAngle={-270}
                    strokeWidth={0}
                  >
                    {pieData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: number) => formatSEK(v)} contentStyle={chartTooltipStyle} />
                </PieChart>
              </ResponsiveContainer>
              <p className="-mt-2 text-xl font-bold text-theme-heading tabular-nums leading-none">
                {formatSharePct(data.market_share_pct)}
              </p>
              <p className="text-[10px] text-theme-muted mt-0.5">Vår andel</p>
            </div>

            <div className="flex-1 space-y-2 min-w-0">
              <div>
                <p className="text-[11px] text-theme-muted">Vår omsättning</p>
                <p className="text-sm font-semibold text-theme-heading tabular-nums leading-tight">{formatSEK(data.supplier_revenue)}</p>
              </div>
              <div>
                <p className="text-[11px] text-theme-muted">Kategoritotal</p>
                <p className="text-sm font-semibold text-theme-heading tabular-nums leading-tight">{formatSEK(data.category_total_revenue)}</p>
              </div>
              {data.competitor_count > 0 && (
                <p className="text-[10px] text-theme-faint leading-snug pt-0.5">
                  Konkurrentdata visas aggregerat
                </p>
              )}
            </div>
          </div>
        )}
      </CardBody>
    </Card>
  )
}
