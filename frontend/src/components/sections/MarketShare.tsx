import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import type { MarketShareResponse } from '../../api/types'
import { formatSEK, formatPct } from '../../utils/format'
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
}

export function MarketShare({
  data,
  loading,
  error,
  onRetry,
  supplierCategory,
}: MarketShareProps) {
  const { chart, chartTooltipStyle } = useChartTheme()

  const pieData = data
    ? [
        { name: 'Vår andel', value: data.supplier_revenue, color: chart.barPrimary },
        { name: 'Konkurrenter (aggregat)', value: data.competitor_aggregate_revenue ?? 0, color: chart.pieMuted },
      ]
    : []

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
          <div className="space-y-3">
            <div className="flex justify-center">
              <Skeleton className="w-36 h-36 rounded-full" />
            </div>
            <Skeleton className="h-4 w-1/2 mx-auto" />
          </div>
        ) : error || !data ? (
          <ErrorState message={error ?? 'Kunde inte hämta data.'} onRetry={onRetry} />
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
                {formatPct(data.market_share_pct)}
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
