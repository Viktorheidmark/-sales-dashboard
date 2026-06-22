import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine,
} from 'recharts'
import type { SalesOverTimeResponse } from '../../api/types'
import { formatSEK, formatPeriod } from '../../utils/format'
import { Card, CardHeader, CardBody } from '../ui/Card'
import { ChartSkeleton } from '../ui/Skeleton'
import { ErrorState } from '../ui/ErrorState'

interface SalesTrendProps {
  data: SalesOverTimeResponse | null
  loading: boolean
  error: string | null
  onRetry: () => void
}

/**
 * Returns the ISO date of the start of the current period for the given
 * granularity. Any series bucket whose period string is >= this value is
 * considered an in-progress (incomplete) period.
 */
function currentPeriodStart(granularity: string): string {
  const now = new Date()
  if (granularity === 'week') {
    // Monday of the current ISO week
    const day = now.getDay() // 0 = Sun
    const diff = day === 0 ? -6 : 1 - day
    const monday = new Date(now)
    monday.setDate(now.getDate() + diff)
    return monday.toISOString().slice(0, 10)
  }
  if (granularity === 'month') {
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`
  }
  // 'day' — today is always potentially incomplete mid-day
  return now.toISOString().slice(0, 10)
}

function CustomTooltip({ active, payload, label, granularity, incompletePeriod }: {
  active?: boolean
  payload?: { value: number }[]
  label?: string
  granularity: string
  incompletePeriod: string | null
}) {
  if (!active || !payload?.length || !label) return null
  const isIncomplete = incompletePeriod && label >= incompletePeriod
  return (
    <div className="bg-white border border-slate-100 shadow-lg rounded-lg px-3.5 py-2.5 text-sm">
      <p className="text-xs text-slate-400 mb-0.5">
        {formatPeriod(label, granularity)}
        {isIncomplete && <span className="ml-1 text-amber-500">· Pågående</span>}
      </p>
      <p className="font-semibold text-slate-900">{formatSEK(payload[0].value)}</p>
    </div>
  )
}

const GRAN_LABELS: Record<string, string> = {
  day: 'Daglig vy',
  week: 'Veckovis vy',
  month: 'Månadsvis vy',
}

const INCOMPLETE_LABELS: Record<string, string> = {
  day: 'dag',
  week: 'vecka',
  month: 'månad',
}

export function SalesTrend({ data, loading, error, onRetry }: SalesTrendProps) {
  if (loading) return <ChartSkeleton height={280} />

  if (error || !data) {
    return (
      <Card>
        <CardHeader><h2 className="text-sm font-semibold text-slate-800">Försäljningstrend</h2></CardHeader>
        <CardBody><ErrorState message={error ?? 'Kunde inte hämta data.'} onRetry={onRetry} /></CardBody>
      </Card>
    )
  }

  const gran = data.granularity
  const periodStart = currentPeriodStart(gran)

  const allPoints = data.series.map(pt => ({
    period: pt.period,
    revenue: pt.revenue ?? 0,
  }))

  // Separate completed vs in-progress buckets
  const completedPoints = allPoints.filter(pt => pt.period < periodStart)
  const hasIncompleteTail = allPoints.length > completedPoints.length

  // Use completed points only for the chart to avoid misleading dips
  const chartData = completedPoints.length > 0 ? completedPoints : allPoints
  const excludeNote = hasIncompleteTail && completedPoints.length > 0
    ? ` · Exkl. pågående ${INCOMPLETE_LABELS[gran] ?? gran}`
    : null

  const avgRevenue = chartData.length
    ? chartData.reduce((s, d) => s + d.revenue, 0) / chartData.length
    : 0

  const total = chartData.reduce((s, d) => s + d.revenue, 0)

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">Försäljningstrend</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              {GRAN_LABELS[gran] ?? gran} · Total {formatSEK(total)}
              {excludeNote && <span className="text-amber-500/80">{excludeNote}</span>}
            </p>
          </div>
          <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest">
            {gran === 'day' ? 'Dag' : gran === 'week' ? 'Vecka' : 'Månad'}
          </span>
        </div>
      </CardHeader>
      <CardBody>
        {chartData.length === 0 ? (
          <div className="flex items-center justify-center h-40 text-sm text-slate-400">
            Inga försäljningsdata för vald period
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                dataKey="period"
                tickFormatter={v => formatPeriod(v, gran)}
                tick={{ fontSize: 11, fill: '#94a3b8' }}
                tickLine={false}
                axisLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                tickFormatter={v => formatSEK(v)}
                tick={{ fontSize: 11, fill: '#94a3b8' }}
                tickLine={false}
                axisLine={false}
                width={72}
              />
              <Tooltip content={
                <CustomTooltip granularity={gran} incompletePeriod={hasIncompleteTail ? periodStart : null} />
              } />
              <ReferenceLine
                y={avgRevenue}
                stroke="#cbd5e1"
                strokeDasharray="4 2"
                label={{ value: 'snitt', position: 'right', fontSize: 10, fill: '#94a3b8' }}
              />
              <Line
                type="monotone"
                dataKey="revenue"
                stroke="#4169e1"
                strokeWidth={2.5}
                dot={chartData.length <= 14}
                activeDot={{ r: 5, fill: '#4169e1', strokeWidth: 0 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </CardBody>
    </Card>
  )
}
