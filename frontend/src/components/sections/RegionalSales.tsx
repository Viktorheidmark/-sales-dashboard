import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Cell,
} from 'recharts'
import type { RegionsResponse } from '../../api/types'
import { formatSEK, formatNumber } from '../../utils/format'
import { useChartTheme, type ChartTokens } from '../../utils/chartTheme'
import { Card, CardHeader, CardBody } from '../ui/Card'
import { ChartSkeleton } from '../ui/Skeleton'
import { ErrorState } from '../ui/ErrorState'

interface RegionalSalesProps {
  data: RegionsResponse | null
  loading: boolean
  error: string | null
  onRetry: () => void
  compact?: boolean
}

function RegionTooltip({ active, payload, chart }: {
  active?: boolean
  payload?: { payload: { region: string; revenue: number; orders: number } }[]
  chart: ChartTokens
}) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div
      className="rounded-lg px-3 py-2 text-sm"
      style={{ backgroundColor: chart.tooltipBg, border: `1px solid ${chart.tooltipBorder}` }}
    >
      <p className="font-semibold" style={{ color: chart.tooltipText }}>{d.region}</p>
      <p className="text-brand-600 dark:text-brand-400 font-medium">{formatSEK(d.revenue)}</p>
      <p className="text-xs mt-0.5" style={{ color: chart.tooltipMuted }}>{formatNumber(d.orders)} ordrar</p>
    </div>
  )
}

export function RegionalSales({ data, loading, error, onRetry, compact = false }: RegionalSalesProps) {
  const { chart, chartAxisTick } = useChartTheme()
  const chartHeight = compact ? 120 : 160

  if (loading) return <ChartSkeleton height={compact ? 200 : 220} />

  if (error || !data) {
    return (
      <Card>
        <CardHeader><h2 className="text-sm font-semibold text-theme-heading">Försäljning per region</h2></CardHeader>
        <CardBody><ErrorState message={error ?? 'Kunde inte hämta data.'} onRetry={onRetry} /></CardBody>
      </Card>
    )
  }

  const chartData = data.regions.map(r => ({
    region: r.region,
    revenue: r.revenue ?? 0,
    orders: r.orders,
  }))

  const maxRev = chartData[0]?.revenue ?? 1

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-theme-heading">Försäljning per region</h2>
            <p className="text-xs text-theme-muted mt-0.5">Rankade efter omsättning</p>
          </div>
          {data.regions[0] && !compact && (
            <span className="text-xs text-brand-600 dark:text-brand-400 font-medium bg-brand-500/10 border border-brand-500/20 px-2 py-1 rounded-md">
              {data.regions[0].region} #1
            </span>
          )}
        </div>
      </CardHeader>
      <CardBody>
        {chartData.length === 0 ? (
          <p className="text-sm text-theme-muted text-center py-8">Inga regionala försäljningsdata för vald period</p>
        ) : (
          <>
            <ResponsiveContainer width="100%" height={chartHeight}>
              <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={chart.grid} vertical={false} />
                <XAxis dataKey="region" tick={chartAxisTick} tickLine={false} axisLine={false} />
                <YAxis tickFormatter={v => formatSEK(v)} tick={chartAxisTick} tickLine={false} axisLine={false} width={68} />
                <Tooltip content={<RegionTooltip chart={chart} />} />
                <Bar dataKey="revenue" radius={[3, 3, 0, 0]} maxBarSize={52}>
                  {chartData.map((entry, i) => (
                    <Cell key={entry.region} fill={i === 0 ? chart.barPrimary : chart.barSecondary} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>

            <div className={`border-t border-workspace-border/60 ${compact ? 'mt-2 pt-2' : 'mt-3 pt-3'}`}>
              <div className="grid grid-cols-[1rem_1fr_4rem_5rem] gap-x-3 mb-1 px-0.5">
                <span />
                <span className="text-xs font-medium text-theme-muted">Region</span>
                <span className="text-xs font-medium text-theme-muted text-right">Ordrar</span>
                <span className="text-xs font-medium text-theme-muted text-right">Omsättning</span>
              </div>
              {data.regions.map((r, i) => (
                <div
                  key={r.region}
                  className={`grid grid-cols-[1rem_1fr_4rem_5rem] gap-x-3 items-center border-b border-workspace-border/50 last:border-0 px-0.5 ${compact ? 'py-1.5' : 'py-2 px-1'}`}
                >
                  <span className={`text-xs font-semibold leading-none ${i === 0 ? 'text-brand-600 dark:text-brand-400' : 'text-theme-muted'}`}>{i + 1}</span>
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-sm font-medium text-theme-strong truncate">{r.region}</span>
                    <div className="h-0.5 flex-1 bg-workspace-border/60 overflow-hidden max-w-[3rem]">
                      <div
                        className="h-full bg-brand-500/70"
                        style={{ width: `${maxRev > 0 ? ((r.revenue ?? 0) / maxRev) * 100 : 0}%` }}
                      />
                    </div>
                  </div>
                  <span className="text-xs text-theme-muted tabular-nums text-right">{formatNumber(r.orders)}</span>
                  <span className="text-sm font-semibold text-theme-heading tabular-nums text-right">{formatSEK(r.revenue)}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </CardBody>
    </Card>
  )
}
