import {
  AreaChart, Area,
  BarChart, Bar, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip,
  PieChart, ResponsiveContainer,
} from 'recharts'
import type { CSSProperties } from 'react'
import type { ChartPayload, ChartHighlights } from '../../api/types'
import { useChartTheme } from '../../utils/chartTheme'
import { formatCompactSEK } from '../../utils/compactCurrency'
import {
  formatSharePct,
  isMarketShareChart,
} from '../../utils/sourcePresentation'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatChartMetric(value: unknown, yKey: string): string {
  const num = Number(value)
  if (Number.isNaN(num)) return String(value ?? '—')
  if (yKey.includes('pct') || yKey.includes('percent')) {
    const sign = num > 0 ? '+' : ''
    return `${sign}${num.toLocaleString('sv-SE', { maximumFractionDigits: 1 })} %`
  }
  return formatCompactSEK(num)
}

function formatPeriodLabel(label: string): string {
  if (!label || label.length < 6) return label
  try {
    const iso = label.length === 7 ? label + '-01' : label
    const d = new Date(iso + 'T00:00:00')
    if (isNaN(d.getTime())) return label
    if (label.length === 7) return d.toLocaleDateString('sv-SE', { month: 'short' })
    return d.toLocaleDateString('sv-SE', { day: 'numeric', month: 'short' })
  } catch {
    return label
  }
}

function formatRevenueTick(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `${Math.round(v / 1_000)}k`
  return String(v)
}

const revenueYAxisDomain: [number, (v: number) => number] = [0, (dataMax) => Math.ceil(dataMax * 1.08)]

function rowLabel(chart: ChartPayload, row: Record<string, unknown>): string {
  const key = chart.tooltip_key || chart.x_key
  return String(row[key] ?? row[chart.x_key] ?? '')
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ChartTooltip({
  active,
  payload,
  label,
  tooltipKey,
  tooltipStyle,
  yKey,
}: {
  active?: boolean
  payload?: Array<{ payload: Record<string, unknown>; value?: number }>
  label?: string
  tooltipKey?: string
  tooltipStyle: CSSProperties
  yKey: string
}) {
  if (!active || !payload?.length) return null
  const row = payload[0].payload
  const displayLabel = tooltipKey && row[tooltipKey] != null
    ? String(row[tooltipKey])
    : String(label ?? row.display_label ?? '')
  const orders = row.orders != null ? Number(row.orders) : null
  const units = row.units != null ? Number(row.units) : null
  return (
    <div style={tooltipStyle} className="px-2.5 py-1.5">
      <p className="text-[11px] font-medium mb-0.5">{displayLabel}</p>
      <p className="text-[11px] tabular-nums">{formatChartMetric(payload[0].value, yKey)}</p>
      {orders != null && !Number.isNaN(orders) && (
        <p className="text-[10px] opacity-70 mt-0.5 tabular-nums">
          {orders.toLocaleString('sv-SE')} ordrar
        </p>
      )}
      {units != null && !Number.isNaN(units) && (
        <p className="text-[10px] opacity-70 mt-0.5 tabular-nums">
          {units.toLocaleString('sv-SE')} st
        </p>
      )}
    </div>
  )
}

/** Readable horizontal ranking — product names / regions visible inline. */
function HorizontalRankChart({
  chart,
  emphasisIndex,
}: {
  chart: ChartPayload
  emphasisIndex: number
}) {
  const yKey = chart.y_key
  const values = chart.data.map(row => Math.abs(Number(row[yKey]) || 0))
  const maxVal = Math.max(...values, 1)
  const isPct = yKey.includes('pct')

  return (
    <div className="space-y-2.5">
      {chart.data.map((row, i) => {
        const isLead = i === emphasisIndex
        const raw = Number(row[yKey])
        const value = Number.isNaN(raw) ? 0 : raw
        const pctWidth = (Math.abs(value) / maxVal) * 100
        const negative = isPct && value < 0
        const name = rowLabel(chart, row)
        return (
          <div key={`${name}-${i}`} className="flex items-center gap-3">
            <div className="flex-1 min-w-0">
              <p className={`text-sm leading-snug truncate ${
                isLead ? 'font-semibold text-theme-heading' : 'font-medium text-theme-strong'
              }`}>
                {name}
              </p>
              <div className="mt-1.5 h-1.5 bg-workspace-border/50 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${
                    negative
                      ? 'bg-red-500/70'
                      : isLead
                        ? 'bg-brand-500/85 dark:bg-brand-400/75'
                        : 'bg-brand-500/40 dark:bg-brand-400/35'
                  }`}
                  style={{ width: `${pctWidth}%` }}
                />
              </div>
            </div>
            <div className="shrink-0 text-right min-w-[4.5rem]">
              <p className={`text-sm font-semibold tabular-nums ${
                negative ? 'text-red-600 dark:text-red-400' : isLead ? 'text-theme-heading' : 'text-theme-body'
              }`}>
                {formatChartMetric(value, yKey)}
              </p>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function TrendHighlightsSummary({ h }: { h: ChartHighlights }) {
  const peakEqTrough = h.peak_label === h.trough_label
  const peakName = h.peak_label_display ?? formatPeriodLabel(h.peak_label)
  const troughName = h.trough_label_display ?? formatPeriodLabel(h.trough_label)
  const gran = h.granularity === 'week' ? 'vecka' : 'månad'
  return (
    <div className="mt-3 pt-3 border-t border-workspace-border/40 grid grid-cols-1 sm:grid-cols-3 gap-3">
      {!peakEqTrough && (
        <>
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-wide text-theme-muted">Högsta {gran}</p>
            <p className="text-sm font-semibold text-theme-heading tabular-nums mt-0.5">
              {formatCompactSEK(h.peak_revenue)}
            </p>
            <p className="text-[11px] text-theme-muted leading-snug break-words mt-0.5">{peakName}</p>
          </div>
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-wide text-theme-muted">Lägsta {gran}</p>
            <p className="text-sm font-semibold text-theme-heading tabular-nums mt-0.5">
              {formatCompactSEK(h.trough_revenue)}
            </p>
            <p className="text-[11px] text-theme-muted leading-snug break-words mt-0.5">{troughName}</p>
          </div>
        </>
      )}
      {h.avg_revenue != null && (
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-wide text-theme-muted">Snitt per {gran}</p>
          <p className="text-sm font-semibold text-theme-heading tabular-nums mt-0.5">
            {formatCompactSEK(h.avg_revenue)}
          </p>
        </div>
      )}
    </div>
  )
}


function AssistantMarketShareChart({
  chart,
}: {
  chart: ChartPayload
  supplierName?: string
}) {
  const { chart: colors, chartTooltipStyle } = useChartTheme()
  const ourRow = chart.data.find(r => r.name === 'Vår andel' || r.name === 'Oss')
  const otherRow = chart.data.find(r => r.name === 'Övriga aktörer' || r.name === 'Konkurrenter')
  const ourRev = Number(ourRow?.[chart.y_key] ?? 0)
  const otherRev = Number(otherRow?.[chart.y_key] ?? 0)
  const total = ourRev + otherRev
  const ourPct = total > 0 ? (ourRev / total) * 100 : 0
  const otherPct = total > 0 ? (otherRev / total) * 100 : 0

  const pieData = [
    { name: 'Vår andel', value: ourRev, color: colors.barPrimary },
    { name: 'Övriga aktörer', value: otherRev, color: colors.pieMuted },
  ]

  return (
    <div className="grid grid-cols-1 sm:grid-cols-[auto_1fr] gap-6 items-center">
      <div className="flex flex-col items-center sm:items-start">
        <div className="relative">
          <PieChart width={132} height={132}>
            <Pie
              data={pieData}
              cx={66}
              cy={66}
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
            <Tooltip formatter={(v: number) => formatCompactSEK(v)} contentStyle={chartTooltipStyle} />
          </PieChart>
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <span className="text-xl font-bold text-theme-heading tabular-nums leading-none">
              {formatSharePct(ourPct)}
            </span>
            <span className="text-[10px] text-theme-muted mt-0.5">Vår andel</span>
          </div>
        </div>
      </div>
      <div className="space-y-3 min-w-0">
        <div>
          <p className="text-xs text-theme-muted">Vår omsättning</p>
          <p className="text-base font-semibold text-theme-heading tabular-nums">{formatCompactSEK(ourRev)}</p>
        </div>
        <div>
          <p className="text-xs text-theme-muted">Kategoritotal</p>
          <p className="text-base font-semibold text-theme-heading tabular-nums">{formatCompactSEK(total)}</p>
        </div>
        <div>
          <p className="text-xs text-theme-muted">Övriga aktörer</p>
          <p className="text-base font-semibold text-theme-heading tabular-nums">{formatSharePct(otherPct)}</p>
        </div>
        <p className="text-[11px] text-theme-faint leading-snug">
          Konkurrentdata visas aggregerat
        </p>
      </div>
    </div>
  )
}

function InsightCard({ chart }: { chart: ChartPayload }) {
  const row = chart.data[0] ?? {}
  const pct = Number(row.revenue_change_pct ?? 0)
  const name = String(row.product_name ?? '')
  const latest = Number(row.latest_period_revenue ?? 0)
  const prior = Number(row.prior_period_revenue ?? 0)
  const change = Number(row.revenue_change ?? latest - prior)
  return (
    <div className="rounded-xl border border-workspace-border bg-workspace-surface px-4 py-4 space-y-3">
      <p className="text-sm font-semibold text-theme-heading leading-snug">{name}</p>
      <p className="text-2xl font-bold tabular-nums leading-none text-red-600 dark:text-red-400">
        {pct.toFixed(1).replace('.', ',')} %
      </p>
      <div className="grid grid-cols-2 gap-3 text-[11px] pt-1 border-t border-workspace-border/50">
        <div>
          <p className="text-theme-muted">Jämförelseperiod</p>
          <p className="font-medium text-theme-body tabular-nums mt-0.5">{formatCompactSEK(prior)}</p>
        </div>
        <div>
          <p className="text-theme-muted">Senaste period</p>
          <p className="font-medium text-theme-body tabular-nums mt-0.5">{formatCompactSEK(latest)}</p>
        </div>
        <div className="col-span-2">
          <p className="text-theme-muted">Absolut förändring</p>
          <p className="font-medium text-red-600 dark:text-red-400 tabular-nums mt-0.5">{formatCompactSEK(change)}</p>
        </div>
      </div>
      {chart.description && (
        <p className="text-xs text-theme-muted leading-relaxed">{chart.description}</p>
      )}
    </div>
  )
}

function EmptyState({ chart }: { chart: ChartPayload }) {
  const positive = chart.source_tool === 'get_declining_products'
  return (
    <div className="rounded-xl border border-workspace-border bg-workspace-surface px-4 py-4 flex items-start gap-3">
      <span className={`text-base leading-none mt-0.5 shrink-0 ${positive ? 'text-emerald-500' : 'text-theme-muted'}`} aria-hidden>
        {positive ? '✓' : '○'}
      </span>
      <div>
        <p className="text-sm font-semibold text-theme-heading">{chart.title || 'Data saknas'}</p>
        <p className="text-xs text-theme-muted mt-1 leading-relaxed">{chart.description}</p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

export function MiniAssistantChart({
  chart,
  supplierName,
  compact = false,
}: {
  chart: ChartPayload
  supplierName?: string
  compact?: boolean
}) {
  const { chart: colors, chartAxisTickSm, chartTooltipStyle } = useChartTheme()

  if (chart.chart_type === 'insight_card') return <InsightCard chart={chart} />
  if (chart.chart_type === 'empty_state') return <EmptyState chart={chart} />

  const isHorizontal = chart.layout === 'horizontal'
  const isDeclineComp = chart.chart_variant === 'decline_comparison'
  const emphasisIndex = chart.emphasis_index ?? 0
  const useRankList = isHorizontal && !isDeclineComp
  const barCount = chart.data.length

  const trendHeight = compact ? 200 : 280
  const chartHeight = chart.chart_type === 'line_chart'
    ? trendHeight
    : isDeclineComp ? 200 : Math.max(120, barCount * 32)

  if (chart.chart_type === 'line_chart') {
    const tickInterval = chart.data.length > 10 ? 'preserveStartEnd' : 0
    const usePreformattedLabels = chart.tooltip_key === 'display_label'
    const showMarkers = chart.show_markers !== false && chart.trend_granularity !== 'day'
    const yDomain = chart.y_axis_from_zero !== false ? revenueYAxisDomain : undefined
    const gradId = `trendAreaFill-${chart.source_tool}`

    return (
      <div>
        <ResponsiveContainer width="100%" height={trendHeight}>
          <AreaChart data={chart.data} margin={{ top: 12, right: 16, left: 4, bottom: 8 }}>
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={colors.line} stopOpacity={0.22} />
              <stop offset="95%" stopColor={colors.line} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} vertical={false} />
          <XAxis
            dataKey={chart.x_key}
            tick={chartAxisTickSm}
            tickLine={false}
            axisLine={false}
            interval={tickInterval}
            tickFormatter={usePreformattedLabels ? undefined : formatPeriodLabel}
            dy={4}
          />
          <YAxis
            tick={chartAxisTickSm}
            tickLine={false}
            axisLine={false}
            width={48}
            tickFormatter={formatRevenueTick}
            domain={yDomain}
          />
          <Tooltip
            content={(
              <ChartTooltip
                tooltipKey={chart.tooltip_key}
                tooltipStyle={chartTooltipStyle as CSSProperties}
                yKey={chart.y_key}
              />
            )}
          />
          <Area
            type="monotone"
            dataKey={chart.y_key}
            stroke={colors.line}
            strokeWidth={showMarkers ? 2.5 : 2}
            fill={`url(#${gradId})`}
            dot={showMarkers ? { r: 3.5, strokeWidth: 2, stroke: colors.line, fill: 'var(--workspace-surface, #fff)' } : false}
            activeDot={{ r: 5, strokeWidth: 0, fill: colors.line }}
          />
          </AreaChart>
        </ResponsiveContainer>
        {chart.highlights && <TrendHighlightsSummary h={chart.highlights} />}
      </div>
    )
  }

  if (chart.chart_type === 'bar_chart') {
    if (isDeclineComp) {
      const prior = Number(chart.data[0]?.[chart.y_key] ?? 0)
      const current = Number(chart.data[1]?.[chart.y_key] ?? 0)
      const change = current - prior
      const changePct = prior > 0 ? ((current - prior) / prior) * 100 : 0
      const isDecline = change < 0

      return (
        <div>
          <div className="w-full" style={{ height: chartHeight }}>
          <ResponsiveContainer width="100%" height={chartHeight}>
            <BarChart
              data={chart.data}
              margin={{ top: 8, right: 16, left: 0, bottom: 4 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} vertical={false} />
              <XAxis dataKey={chart.x_key} tick={chartAxisTickSm} tickLine={false} axisLine={false} />
              <YAxis
                tick={chartAxisTickSm}
                tickLine={false}
                axisLine={false}
                width={44}
                tickFormatter={formatRevenueTick}
                domain={revenueYAxisDomain}
              />
              <Tooltip
                content={(
                  <ChartTooltip
                    tooltipStyle={chartTooltipStyle as CSSProperties}
                    yKey={chart.y_key}
                  />
                )}
              />
              <Bar dataKey={chart.y_key} radius={[4, 4, 0, 0]} barSize={72}>
                {chart.data.map((_, i) => (
                  <Cell
                    key={i}
                    fill={i === 0 ? colors.pieMuted : (isDecline ? '#ef4444' : colors.barPrimary)}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
          <div className="mt-3 pt-3 border-t border-workspace-border/40 grid grid-cols-2 gap-3 text-[11px]">
            <div>
              <p className="text-theme-muted">Absolut förändring</p>
              <p className={`font-semibold tabular-nums mt-0.5 ${isDecline ? 'text-red-600 dark:text-red-400' : 'text-theme-heading'}`}>
                {formatCompactSEK(change)}
              </p>
            </div>
            <div>
              <p className="text-theme-muted">Förändring %</p>
              <p className={`font-semibold tabular-nums mt-0.5 ${isDecline ? 'text-red-600 dark:text-red-400' : 'text-theme-heading'}`}>
                {changePct > 0 ? '+' : ''}{changePct.toLocaleString('sv-SE', { maximumFractionDigits: 1 })} %
              </p>
            </div>
          </div>
        </div>
      )
    }

    if (useRankList) {
      return <HorizontalRankChart chart={chart} emphasisIndex={emphasisIndex} />
    }

    return (
      <div className="w-full" style={{ height: chartHeight }}>
        <ResponsiveContainer width="100%" height={chartHeight}>
          <BarChart
            data={chart.data}
            margin={{ top: 4, right: 8, left: 0, bottom: 4 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} vertical={false} />
            <XAxis dataKey={chart.x_key} tick={chartAxisTickSm} tickLine={false} axisLine={false} />
            <YAxis tick={chartAxisTickSm} tickLine={false} axisLine={false} width={48} />
            <Tooltip
              content={(
                <ChartTooltip
                  tooltipKey={chart.tooltip_key}
                  tooltipStyle={chartTooltipStyle as CSSProperties}
                  yKey={chart.y_key}
                />
              )}
            />
            <Bar dataKey={chart.y_key} radius={[3, 3, 0, 0]} barSize={18}>
              {chart.data.map((_, i) => (
                <Cell
                  key={i}
                  fill={i === emphasisIndex ? colors.barPrimary : colors.barSecondary}
                  fillOpacity={i === emphasisIndex ? 1 : 0.45}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    )
  }

  if (chart.chart_type === 'pie_chart' && isMarketShareChart(chart)) {
    return <AssistantMarketShareChart chart={chart} supplierName={supplierName} />
  }

  if (chart.chart_type === 'pie_chart') {
    return (
      <PieChart width={140} height={140}>
        <Pie
          data={chart.data}
          dataKey={chart.y_key}
          nameKey={chart.x_key}
          cx={70}
          cy={70}
          outerRadius={58}
          strokeWidth={0}
        >
          {chart.data.map((_, i) => (
            <Cell key={i} fill={colors.pieColors[i % colors.pieColors.length]} />
          ))}
        </Pie>
        <Tooltip contentStyle={chartTooltipStyle} />
      </PieChart>
    )
  }

  return null
}
