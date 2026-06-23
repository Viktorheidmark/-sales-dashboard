import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import type { CSSProperties } from 'react'
import type { ChartPayload } from '../../api/types'
import { useChartTheme } from '../../utils/chartTheme'
import { formatCompactSEK } from '../../utils/compactCurrency'
import {
  formatSharePct,
  isMarketShareChart,
  marketShareLegendItems,
} from '../../utils/sourcePresentation'

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

export function MiniAssistantChart({
  chart,
  supplierName,
}: {
  chart: ChartPayload
  supplierName?: string
}) {
  const { chart: colors, chartAxisTickSm, chartTooltipStyle } = useChartTheme()
  const isHorizontal = chart.layout === 'horizontal'
  const isProductChart = isProductComparisonChart(chart)
  const emphasisIndex = chart.emphasis_index ?? 0
  const barCount = chart.data.length
  const chartHeight = isHorizontal ? Math.max(120, barCount * 28 + 20) : 168

  const barData = isProductChart
    ? chart.data.map((row, i) => ({ ...row, rank_label: `#${i + 1}` }))
    : chart.data
  const categoryKey = isProductChart ? 'rank_label' : chart.x_key

  if (chart.chart_type === 'line_chart') {
    return (
      <ResponsiveContainer width="100%" height={chartHeight}>
        <LineChart data={chart.data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
          <XAxis dataKey={chart.x_key} tick={chartAxisTickSm} tickLine={false} axisLine={false} />
          <YAxis tick={chartAxisTickSm} tickLine={false} axisLine={false} width={48} />
          <Tooltip contentStyle={chartTooltipStyle} />
          <Line type="monotone" dataKey={chart.y_key} stroke={colors.line} strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    )
  }

  if (chart.chart_type === 'bar_chart') {
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
              <XAxis type="number" tick={chartAxisTickSm} tickLine={false} axisLine={false} />
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

  if (chart.chart_type === 'pie_chart') {
    return (
      <div>
        <ResponsiveContainer width="100%" height={168}>
          <PieChart>
            <Pie
              data={chart.data}
              dataKey={chart.y_key}
              nameKey={chart.x_key}
              cx="50%"
              cy="50%"
              outerRadius={64}
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
