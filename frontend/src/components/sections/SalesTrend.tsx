import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine,
} from 'recharts'
import type { SalesOverTimeResponse } from '../../api/types'
import { formatSEK, formatPeriod, formatShortDateSv } from '../../utils/format'
import { useChartTheme, type ChartTokens } from '../../utils/chartTheme'
import { useTenantBranding } from '../../context/TenantBrandingContext'
import { Card, CardHeader, CardBody } from '../ui/Card'
import { ChartSkeleton } from '../ui/Skeleton'
import { ErrorState } from '../ui/ErrorState'

interface SalesTrendProps {
  data: SalesOverTimeResponse | null
  loading: boolean
  error: string | null
  onRetry: () => void
  featured?: boolean
  periodContextLabel?: string
  chartHeight?: number
}

function currentPeriodStart(granularity: string): string {
  const now = new Date()
  if (granularity === 'week') {
    const day = now.getDay()
    const diff = day === 0 ? -6 : 1 - day
    const monday = new Date(now)
    monday.setDate(now.getDate() + diff)
    return monday.toISOString().slice(0, 10)
  }
  if (granularity === 'month') {
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`
  }
  return now.toISOString().slice(0, 10)
}

function CustomTooltip({ active, payload, label, granularity, incompletePeriod, chart }: {
  active?: boolean
  payload?: { value: number }[]
  label?: string
  granularity: string
  incompletePeriod: string | null
  chart: ChartTokens
}) {
  if (!active || !payload?.length || !label) return null
  const isIncomplete = incompletePeriod && label >= incompletePeriod
  return (
    <div
      className="rounded-lg px-3.5 py-2.5 text-sm"
      style={{ backgroundColor: chart.tooltipBg, border: `1px solid ${chart.tooltipBorder}` }}
    >
      <p className="text-xs mb-0.5" style={{ color: chart.tooltipMuted }}>
        {formatPeriod(label, granularity)}
        {isIncomplete && <span className="ml-1 text-amber-500 dark:text-amber-400">· Pågående</span>}
      </p>
      <p className="font-semibold" style={{ color: chart.tooltipText }}>{formatSEK(payload[0].value)}</p>
    </div>
  )
}

const GRAN_SUBTITLES: Record<string, string> = {
  day: 'Daglig omsättning',
  week: 'Veckovis omsättning',
  month: 'Månadsvis omsättning',
}

const INCOMPLETE_NOTES: Record<string, string> = {
  day: 'Pågående dag exkluderad.',
  week: 'Pågående vecka exkluderad.',
  month: 'Pågående månad exkluderad.',
}

export function SalesTrend({ data, loading, error, onRetry, featured = false, periodContextLabel, chartHeight: chartHeightProp }: SalesTrendProps) {
  const { chart, chartAxisTick } = useChartTheme()
  const { chartPrimary } = useTenantBranding()
  const chartHeight = chartHeightProp ?? (featured ? 280 : 280)
  const headerPad = featured ? 'px-5 pt-5 pb-3' : undefined
  const bodyPad = featured ? 'px-5 pb-5' : undefined

  if (loading) return <ChartSkeleton height={chartHeight} />

  if (error || !data) {
    return (
      <Card>
        <CardHeader className={headerPad}>
          <h2 className="text-sm font-semibold text-theme-heading">Försäljningstrend</h2>
        </CardHeader>
        <CardBody className={bodyPad}><ErrorState message={error ?? 'Kunde inte hämta data.'} onRetry={onRetry} /></CardBody>
      </Card>
    )
  }

  const gran = data.granularity
  const periodStart = currentPeriodStart(gran)

  const allPoints = data.series.map(pt => ({
    period: pt.period,
    revenue: pt.revenue ?? 0,
  }))

  const completedPoints = allPoints.filter(pt => pt.period < periodStart)
  const hasIncompleteTail = allPoints.length > completedPoints.length
  const chartData = completedPoints.length > 0 ? completedPoints : allPoints
  const showIncompleteNote = hasIncompleteTail && completedPoints.length > 0
  const incompleteNote = showIncompleteNote
    ? INCOMPLETE_NOTES[gran] ?? 'Pågående period exkluderad.'
    : null

  const avgRevenue = chartData.length
    ? chartData.reduce((s, d) => s + d.revenue, 0) / chartData.length
    : 0

  const granSubtitle = GRAN_SUBTITLES[gran] ?? 'Omsättning'
  const dr = data.date_range
  const periodPart =
    periodContextLabel === 'Hela tillgängliga perioden' && dr?.start && dr?.end
      ? `${formatShortDateSv(dr.start)} – ${formatShortDateSv(dr.end)}`
      : periodContextLabel
  const metadataLine = periodPart ? `${periodPart} · ${granSubtitle}` : granSubtitle

  return (
    <Card className={featured ? 'h-full' : ''}>
      <CardHeader className={headerPad}>
        <div>
          <h2 className="text-sm font-semibold text-theme-heading">Försäljningstrend</h2>
          <p className="text-xs text-theme-muted mt-1 leading-relaxed">
            {metadataLine}
          </p>
        </div>
      </CardHeader>
      <CardBody className={bodyPad}>
        {chartData.length === 0 ? (
          <div className="flex items-center justify-center h-40 text-sm text-theme-muted">
            Inga försäljningsdata för vald period
          </div>
        ) : (
          <>
          <ResponsiveContainer width="100%" height={chartHeight}>
            <LineChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={chart.grid} />
              <XAxis
                dataKey="period"
                tickFormatter={v => formatPeriod(v, gran)}
                tick={chartAxisTick}
                tickLine={false}
                axisLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                tickFormatter={v => formatSEK(v)}
                tick={chartAxisTick}
                tickLine={false}
                axisLine={false}
                width={72}
              />
              <Tooltip content={
                <CustomTooltip
                  granularity={gran}
                  incompletePeriod={hasIncompleteTail ? periodStart : null}
                  chart={chart}
                />
              } />
              <ReferenceLine
                y={avgRevenue}
                stroke={chart.referenceLine}
                strokeDasharray="4 2"
                label={{ value: 'snitt', position: 'right', fontSize: 10, fill: chart.axis }}
              />
              <Line
                type="monotone"
                dataKey="revenue"
                stroke={chartPrimary}
                strokeWidth={2.5}
                dot={chartData.length <= 14 ? { fill: chartPrimary, r: 3, strokeWidth: 0 } : false}
                activeDot={{ r: 5, fill: chartPrimary, strokeWidth: 0 }}
              />
            </LineChart>
          </ResponsiveContainer>
          {incompleteNote && (
            <p className="mt-2 text-[11px] text-theme-faint leading-snug">
              {incompleteNote}
            </p>
          )}
          </>
        )}
      </CardBody>
    </Card>
  )
}
