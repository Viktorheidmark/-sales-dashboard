import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine,
} from 'recharts'
import type { SalesOverTimeResponse } from '../../api/types'
import { formatSEK, formatPeriod } from '../../utils/format'
import { Card, CardHeader, CardBody } from '../ui/Card'
import { ChartSkeleton } from '../ui/Skeleton'
import { ErrorState } from '../ui/ErrorState'
import { MetaFooter } from '../ui/MetaFooter'

interface SalesTrendProps {
  data: SalesOverTimeResponse | null
  loading: boolean
  error: string | null
  onRetry: () => void
}

function CustomTooltip({ active, payload, label, granularity }: {
  active?: boolean
  payload?: { value: number }[]
  label?: string
  granularity: string
}) {
  if (!active || !payload?.length || !label) return null
  return (
    <div className="bg-white border border-zinc-200 shadow-lg rounded-lg px-3 py-2 text-sm">
      <p className="font-medium text-zinc-700">{formatPeriod(label, granularity)}</p>
      <p className="text-brand-600 font-semibold">{formatSEK(payload[0].value)}</p>
    </div>
  )
}

export function SalesTrend({ data, loading, error, onRetry }: SalesTrendProps) {
  if (loading) return <ChartSkeleton height={280} />

  if (error || !data) {
    return (
      <Card>
        <CardHeader><h2 className="text-sm font-semibold text-zinc-700">Försäljningstrend</h2></CardHeader>
        <CardBody><ErrorState message={error ?? 'Kunde inte hämta data.'} onRetry={onRetry} /></CardBody>
      </Card>
    )
  }

  const gran = data.granularity
  const chartData = data.series.map(pt => ({
    period: pt.period,
    revenue: pt.revenue ?? 0,
    label: formatPeriod(pt.period, gran),
  }))

  const avgRevenue = chartData.length
    ? chartData.reduce((s, d) => s + d.revenue, 0) / chartData.length
    : 0

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-zinc-700">Försäljningstrend</h2>
          <span className="text-xs text-zinc-400 capitalize">{gran === 'day' ? 'Dag' : gran === 'week' ? 'Vecka' : 'Månad'}</span>
        </div>
      </CardHeader>
      <CardBody>
        {chartData.length === 0 ? (
          <div className="flex items-center justify-center h-40 text-sm text-zinc-400">
            Inga försäljningsdata för vald period
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" />
              <XAxis
                dataKey="period"
                tickFormatter={v => formatPeriod(v, gran)}
                tick={{ fontSize: 11, fill: '#a1a1aa' }}
                tickLine={false}
                axisLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                tickFormatter={v => formatSEK(v)}
                tick={{ fontSize: 11, fill: '#a1a1aa' }}
                tickLine={false}
                axisLine={false}
                width={72}
              />
              <Tooltip content={<CustomTooltip granularity={gran} />} />
              <ReferenceLine
                y={avgRevenue}
                stroke="#d4d4d8"
                strokeDasharray="4 2"
                label={{ value: 'snitt', position: 'right', fontSize: 10, fill: '#a1a1aa' }}
              />
              <Line
                type="monotone"
                dataKey="revenue"
                stroke="#4169e1"
                strokeWidth={2.5}
                dot={chartData.length <= 12}
                activeDot={{ r: 5, fill: '#4169e1' }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
        <MetaFooter
          source={data.source}
          generatedAt={data.generated_at}
          rowCount={data.row_count}
        />
      </CardBody>
    </Card>
  )
}
