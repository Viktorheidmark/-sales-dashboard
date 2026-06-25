import {
  ResponsiveContainer, ComposedChart, Line, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine,
} from 'recharts'
import type { SalesOverTimeResponse } from '../../api/types'
import { formatSEK, formatPeriod, formatShortDateSv, formatWeekRange } from '../../utils/format'
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

interface ChartPoint {
  period: string
  revenue: number
  revenueMain: number | null
  revenuePartial: number | null
  revenueArea: number | null
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

function buildChartPoints(
  series: SalesOverTimeResponse['series'],
  granularity: string,
  includeIncompleteWeek: boolean,
): { chartData: ChartPoint[]; hasIncompleteTail: boolean; incompletePeriodStart: string | null } {
  const periodStart = currentPeriodStart(granularity)
  const allPoints = series.map(pt => ({
    period: pt.period,
    revenue: pt.revenue ?? 0,
  }))

  const hasIncompleteTail = allPoints.some(pt => pt.period >= periodStart)

  if (!includeIncompleteWeek) {
    const completedPoints = allPoints.filter(pt => pt.period < periodStart)
    const chartData = (completedPoints.length > 0 ? completedPoints : allPoints).map(pt => ({
      ...pt,
      revenueMain: pt.revenue,
      revenuePartial: null,
      revenueArea: pt.revenue,
    }))
    return {
      chartData,
      hasIncompleteTail: hasIncompleteTail && completedPoints.length > 0,
      incompletePeriodStart: null,
    }
  }

  const incompleteIdx = allPoints.findIndex(pt => pt.period >= periodStart)
  const chartData: ChartPoint[] = allPoints.map((pt, i) => {
    const isIncomplete = hasIncompleteTail && incompleteIdx >= 0 && i >= incompleteIdx
    return {
      period: pt.period,
      revenue: pt.revenue,
      revenueMain: isIncomplete ? null : pt.revenue,
      revenuePartial: null,
      revenueArea: isIncomplete ? null : pt.revenue,
    }
  })

  if (hasIncompleteTail && incompleteIdx >= 0) {
    chartData[incompleteIdx].revenuePartial = chartData[incompleteIdx].revenue
    if (incompleteIdx > 0) {
      chartData[incompleteIdx - 1].revenuePartial = chartData[incompleteIdx - 1].revenue
    }
  }

  return {
    chartData,
    hasIncompleteTail,
    incompletePeriodStart: hasIncompleteTail ? periodStart : null,
  }
}

function xAxisInterval(granularity: string, pointCount: number): number | 'preserveStartEnd' {
  if (granularity === 'week' && pointCount > 20) return 6
  return 'preserveStartEnd'
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
  const isIncomplete = incompletePeriod != null && label >= incompletePeriod
  const periodLabel = granularity === 'week'
    ? formatWeekRange(label)
    : formatPeriod(label, granularity)

  return (
    <div
      className="rounded-lg px-3.5 py-2.5 text-sm"
      style={{ backgroundColor: chart.tooltipBg, border: `1px solid ${chart.tooltipBorder}` }}
    >
      <p className="text-xs mb-0.5" style={{ color: chart.tooltipMuted }}>
        {periodLabel}
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

  if (loading) return <ChartSkeleton height={chartHeight} />

  if (error || !data) {
    return (
      <Card variant="dashboard">
        <CardHeader>
          <h2 className="dashboard-panel-title">Försäljningstrend</h2>
        </CardHeader>
        <CardBody><ErrorState message={error ?? 'Kunde inte hämta data.'} onRetry={onRetry} /></CardBody>
      </Card>
    )
  }

  const gran = data.granularity
  const isAllTimeWeekly = gran === 'week' && periodContextLabel === 'Hela tillgängliga perioden'
  const includeIncompleteWeek = isAllTimeWeekly

  const { chartData, hasIncompleteTail, incompletePeriodStart } = buildChartPoints(
    data.series,
    gran,
    includeIncompleteWeek,
  )

  const showIncompleteNote = includeIncompleteWeek
    ? hasIncompleteTail
    : hasIncompleteTail && chartData.length > 0

  const incompleteNote = showIncompleteNote
    ? (includeIncompleteWeek
      ? 'Pågående vecka visas med preliminära siffror.'
      : INCOMPLETE_NOTES[gran] ?? 'Pågående period exkluderad.')
    : null

  const avgRevenue = chartData.length
    ? chartData.reduce((s, d) => s + d.revenue, 0) / chartData.length
    : 0

  const metadataLine = isAllTimeWeekly
    ? 'Omsättning per vecka · hela tillgängliga perioden'
    : (() => {
      const granSubtitle = GRAN_SUBTITLES[gran] ?? 'Omsättning'
      const dr = data.date_range
      const periodPart =
        periodContextLabel === 'Hela tillgängliga perioden' && dr?.start && dr?.end
          ? `${formatShortDateSv(dr.start)} – ${formatShortDateSv(dr.end)}`
          : periodContextLabel
      return periodPart ? `${periodPart} · ${granSubtitle}` : granSubtitle
    })()

  const strokeWidth = gran === 'week' && chartData.length > 20 ? 2 : 2.5
  const showDots = chartData.length <= 14
  const areaGradId = 'overview-trend-area-fill'

  return (
    <Card variant="dashboard" className={featured ? 'h-full' : ''}>
      <CardHeader>
        <div>
          <h2 className="dashboard-panel-title">Försäljningstrend</h2>
          <p className="dashboard-panel-subtitle">
            {metadataLine}
          </p>
        </div>
      </CardHeader>
      <CardBody>
        {chartData.length === 0 ? (
          <div className="flex items-center justify-center h-40 text-sm text-theme-muted">
            Inga försäljningsdata för vald period
          </div>
        ) : (
          <>
          <ResponsiveContainer width="100%" height={chartHeight}>
            <ComposedChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
              <defs>
                <linearGradient id={areaGradId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={chartPrimary} stopOpacity={0.2} />
                  <stop offset="95%" stopColor={chartPrimary} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={chart.grid} />
              <XAxis
                dataKey="period"
                tickFormatter={v => formatPeriod(v, gran)}
                tick={chartAxisTick}
                tickLine={false}
                axisLine={false}
                interval={xAxisInterval(gran, chartData.length)}
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
                  incompletePeriod={incompletePeriodStart}
                  chart={chart}
                />
              } />
              <ReferenceLine
                y={avgRevenue}
                stroke={chart.referenceLine}
                strokeDasharray="4 2"
                label={{ value: 'snitt', position: 'right', fontSize: 10, fill: chart.axis }}
              />
              <Area
                type="monotone"
                dataKey="revenueArea"
                stroke="none"
                fill={`url(#${areaGradId})`}
                connectNulls={false}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="revenueMain"
                stroke={chartPrimary}
                strokeWidth={strokeWidth}
                connectNulls={false}
                dot={showDots ? { fill: chartPrimary, r: 3, strokeWidth: 0 } : false}
                activeDot={{ r: 5, fill: chartPrimary, strokeWidth: 0 }}
                isAnimationActive={false}
              />
              {includeIncompleteWeek && hasIncompleteTail && (
                <Line
                  type="monotone"
                  dataKey="revenuePartial"
                  stroke={chartPrimary}
                  strokeWidth={strokeWidth}
                  strokeDasharray="5 4"
                  strokeOpacity={0.55}
                  connectNulls
                  dot={(props) => {
                    const { cx, cy, index } = props
                    if (index !== chartData.length - 1 || cx == null || cy == null) {
                      return <g />
                    }
                    return (
                      <circle
                        cx={cx}
                        cy={cy}
                        r={3.5}
                        fill={chartPrimary}
                        fillOpacity={0.45}
                        stroke="none"
                      />
                    )
                  }}
                  activeDot={{ r: 5, fill: chartPrimary, fillOpacity: 0.55, strokeWidth: 0 }}
                  isAnimationActive={false}
                />
              )}
            </ComposedChart>
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
