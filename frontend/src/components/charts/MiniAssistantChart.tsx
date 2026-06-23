import {
  AreaChart, Area,
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import type { CSSProperties } from 'react'
import type { ChartPayload, ChartHighlights } from '../../api/types'
import { useChartTheme } from '../../utils/chartTheme'
import { formatCompactSEK } from '../../utils/compactCurrency'
import {
  formatSharePct,
  isMarketShareChart,
  marketShareLegendItems,
} from '../../utils/sourcePresentation'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isProductComparisonChart(chart: ChartPayload): boolean {
  return (
    chart.chart_type === 'bar_chart'
    && chart.layout === 'horizontal'
    && chart.tooltip_key === 'product_name'
  )
}

function formatChartMetric(value: unknown, yKey: string): string {
  const num = Number(value)
  if (Number.isNaN(num)) return String(value ?? '—')
  if (yKey.includes('pct') || yKey.includes('percent')) {
    return `${num.toLocaleString('sv-SE', { maximumFractionDigits: 1 })} %`
  }
  return formatCompactSEK(num)
}

/** Format ISO date label for chart axis — "2026-05-19" → "19 maj", "2026-05" → "maj" */
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

/** Compact revenue tick: "45k", "1.2M" */
function formatRevenueTick(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `${Math.round(v / 1_000)}k`
  return String(v)
}

/** Y-axis domain — honest absolute scale from zero */
const revenueYAxisDomain: [number, (v: number) => number] = [0, (dataMax) => Math.ceil(dataMax * 1.08)]

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ProductRankList({
  chart,
  emphasisIndex,
}: {
  chart: ChartPayload
  emphasisIndex: number
}) {
  const nameKey = chart.tooltip_key!
  const valueKey = chart.y_key
  return (
    <ol className="mt-2.5 space-y-1 border-t border-workspace-border/50 pt-2.5">
      {chart.data.map((row, i) => {
        const isLead = i === emphasisIndex
        return (
          <li
            key={i}
            className={`flex items-baseline gap-2 text-[11px] leading-snug ${
              isLead ? 'font-medium text-theme-heading' : 'text-theme-body'
            }`}
          >
            <span className={`shrink-0 tabular-nums w-5 ${isLead ? 'text-brand-500' : 'text-theme-muted'}`}>
              #{i + 1}
            </span>
            <span className="min-w-0 flex-1">{String(row[nameKey] ?? '')}</span>
            <span className={`shrink-0 tabular-nums ${isLead ? 'text-theme-heading' : 'text-theme-muted'}`}>
              {formatChartMetric(row[valueKey], valueKey)}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

function MarketShareLegend({ chart, supplierName }: { chart: ChartPayload; supplierName?: string }) {
  const { chart: colors } = useChartTheme()
  const legend = marketShareLegendItems(chart, supplierName)
  if (!legend) return null
  return (
    <div className="flex flex-wrap gap-x-5 gap-y-1.5 mt-3 pt-3 border-t border-workspace-border/60">
      <span className="inline-flex items-center gap-2 text-xs text-theme-body">
        <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: colors.barPrimary }} aria-hidden />
        {legend.supplierLabel}: {formatSharePct(legend.supplierPct)}
      </span>
      <span className="inline-flex items-center gap-2 text-xs text-theme-body">
        <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: colors.pieMuted }} aria-hidden />
        Övriga aktörer: {formatSharePct(legend.othersPct)}
      </span>
    </div>
  )
}

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
  return (
    <div style={tooltipStyle} className="px-2.5 py-1.5">
      <p className="text-[11px] font-medium mb-0.5">{displayLabel}</p>
      <p className="text-[11px] opacity-80">{formatChartMetric(payload[0].value, yKey)}</p>
    </div>
  )
}

/** Peak/trough/change summary shown below a trend chart. */
function TrendHighlightsSummary({ h }: { h: ChartHighlights }) {
  const positive = h.change_pct >= 0
  const sign = positive ? '+' : ''
  const pctStr = `${sign}${h.change_pct.toFixed(1)} %`
  const peakEqTrough = h.peak_label === h.trough_label
  return (
    <div className="mt-2 pt-2 border-t border-workspace-border/40 flex flex-wrap gap-x-5 gap-y-0.5">
      {!peakEqTrough && (
        <>
          <span className="text-[11px] text-theme-muted">
            Starkaste:{' '}
            <span className="font-medium text-theme-body">{formatCompactSEK(h.peak_revenue)}</span>
            <span className="opacity-50"> ({formatPeriodLabel(h.peak_label)})</span>
          </span>
          <span className="text-[11px] text-theme-muted">
            Svagaste:{' '}
            <span className="font-medium text-theme-body">{formatCompactSEK(h.trough_revenue)}</span>
            <span className="opacity-50"> ({formatPeriodLabel(h.trough_label)})</span>
          </span>
        </>
      )}
      <span className="text-[11px] text-theme-muted">
        Periodutveckling:{' '}
        <span className={`font-medium ${positive ? 'text-emerald-500 dark:text-emerald-400' : 'text-red-500 dark:text-red-400'}`}>
          {pctStr}
        </span>
      </span>
    </div>
  )
}

/** Fallback insight card (only rendered when revenue figures are missing from MCP response) */
function InsightCard({ chart }: { chart: ChartPayload }) {
  const row = chart.data[0] ?? {}
  const pct  = Number(row.revenue_change_pct ?? 0)
  const name = String(row.product_name ?? '')
  return (
    <div className="rounded-lg border border-workspace-border bg-workspace-surface px-4 py-4 space-y-2">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-theme-muted">{chart.title}</p>
      <p className="text-sm font-semibold text-theme-heading">{name}</p>
      <p className="text-[2rem] font-bold tabular-nums leading-none text-red-500 dark:text-red-400">
        {pct.toFixed(1)} %
      </p>
      <p className="text-xs text-theme-muted">{chart.description}</p>
    </div>
  )
}

/** Compact positive empty state when no products are declining. */
function EmptyState({ chart }: { chart: ChartPayload }) {
  return (
    <div className="rounded-lg border border-workspace-border bg-workspace-surface px-4 py-4 flex items-start gap-3">
      <span className="text-emerald-500 text-base leading-none mt-0.5 shrink-0" aria-hidden>✓</span>
      <div>
        <p className="text-sm font-semibold text-theme-heading">{chart.title}</p>
        <p className="text-xs text-theme-muted mt-0.5 leading-relaxed">{chart.description}</p>
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

  // Self-contained non-Recharts types
  if (chart.chart_type === 'insight_card') return <InsightCard chart={chart} />
  if (chart.chart_type === 'empty_state')  return <EmptyState  chart={chart} />

  const isHorizontal     = chart.layout === 'horizontal'
  const isProductChart   = isProductComparisonChart(chart)
  const isDeclineComp    = chart.chart_variant === 'decline_comparison'
  const emphasisIndex    = chart.emphasis_index ?? 0
  const barCount         = chart.data.length
  const chartHeight      = chart.chart_type === 'line_chart'
    ? (compact ? 120 : 160)
    : isHorizontal
      ? Math.max(100, barCount * 28 + 16)
      : isDeclineComp ? 168 : 156

  const barData     = isProductChart
    ? chart.data.map((row, i) => ({ ...row, rank_label: `#${i + 1}` }))
    : chart.data
  const categoryKey = isProductChart ? 'rank_label' : chart.x_key

  // ── Area chart (time-series trend) ──────────────────────────────────────
  if (chart.chart_type === 'line_chart') {
    const tickInterval = chart.data.length > 8 ? 'preserveStartEnd' : 0
    const gradId = 'trendAreaFill'
    return (
      <div>
        <ResponsiveContainer width="100%" height={chartHeight}>
          <AreaChart data={chart.data} margin={{ top: 8, right: 8, left: 0, bottom: 2 }}>
            <defs>
              <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor={colors.line} stopOpacity={0.18} />
                <stop offset="90%" stopColor={colors.line} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
            <XAxis
              dataKey={chart.x_key}
              tick={chartAxisTickSm}
              tickLine={false}
              axisLine={false}
              interval={tickInterval}
              tickFormatter={formatPeriodLabel}
            />
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
              strokeWidth={2}
              fill={`url(#${gradId})`}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 0 }}
            />
          </AreaChart>
        </ResponsiveContainer>
        {chart.highlights && <TrendHighlightsSummary h={chart.highlights} />}
      </div>
    )
  }

  // ── Bar chart ────────────────────────────────────────────────────────────
  if (chart.chart_type === 'bar_chart') {

    // Decline comparison: 2 vertical bars — prior (muted) → current (red)
    if (isDeclineComp) {
      return (
        <ResponsiveContainer width="100%" height={chartHeight}>
          <BarChart data={chart.data} margin={{ top: 8, right: 16, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} vertical={false} />
            <XAxis
              dataKey={chart.x_key}
              tick={chartAxisTickSm}
              tickLine={false}
              axisLine={false}
            />
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
                  fill={i === 0 ? colors.barSecondary : '#ef4444'}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )
    }

    // Horizontal ranked bar (top products, regions, multi-decline)
    if (isHorizontal) {
      return (
        <div>
          <ResponsiveContainer width="100%" height={chartHeight}>
            <BarChart
              data={barData}
              layout="vertical"
              margin={{ top: 4, right: 12, left: 0, bottom: 4 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} horizontal={false} />
              <XAxis
                type="number"
                tick={chartAxisTickSm}
                tickLine={false}
                axisLine={false}
                tickFormatter={chart.y_key.includes('pct') ? (v: number) => `${v} %` : undefined}
              />
              <YAxis
                type="category"
                dataKey={categoryKey}
                tick={{ ...chartAxisTickSm, style: { whiteSpace: 'nowrap' } }}
                tickLine={false}
                axisLine={false}
                width={isProductChart ? 28 : 108}
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
              <Bar dataKey={chart.y_key} radius={[0, 3, 3, 0]} barSize={16}>
                {barData.map((_, i) => (
                  <Cell
                    key={i}
                    fill={i === emphasisIndex ? colors.barPrimary : colors.barSecondary}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          {isProductChart && (
            <ProductRankList chart={chart} emphasisIndex={emphasisIndex} />
          )}
        </div>
      )
    }

    // Vertical bar (fallback)
    return (
      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart data={chart.data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
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
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    )
  }

  // ── Pie chart (market share) ─────────────────────────────────────────────
  if (chart.chart_type === 'pie_chart') {
    return (
      <div>
        <ResponsiveContainer width="100%" height={160}>
          <PieChart>
            <Pie
              data={chart.data}
              dataKey={chart.y_key}
              nameKey={chart.x_key}
              cx="50%"
              cy="50%"
              outerRadius={62}
              strokeWidth={0}
            >
              {chart.data.map((_, i) => (
                <Cell key={i} fill={colors.pieColors[i % colors.pieColors.length]} />
              ))}
            </Pie>
            <Tooltip contentStyle={chartTooltipStyle} />
          </PieChart>
        </ResponsiveContainer>
        {isMarketShareChart(chart) && <MarketShareLegend chart={chart} supplierName={supplierName} />}
      </div>
    )
  }

  return null
}
