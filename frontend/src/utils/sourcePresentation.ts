import type { ChartPayload, ChatResponse, DateRange, SourceMeta } from '../api/types'

const TOOL_LABELS_SV: Record<string, string> = {
  get_market_share: 'Marknadsandelsanalys',
  get_sales_over_time: 'Försäljningsanalys',
  get_top_products: 'Produktanalys',
  get_sales_by_region: 'Regional analys',
  get_declining_products: 'Nedgångsanalys',
  get_overview: 'Försäljningsanalys',
}

export const ANALYTICS_DATA_SOURCE = 'Solvigo Analytics'

const AGGREGATE_COMPETITOR_RE =
  /konkurrentdata\s+visas\s+endast\s+(aggregerat|på\s+aggregerad\s+nivå)/i

export function toolLabelSv(tool: string): string {
  return TOOL_LABELS_SV[tool] ?? tool.replace(/^get_/, '').replace(/_/g, ' ')
}

export function isAggregateCompetitorLimitation(text: string): boolean {
  return AGGREGATE_COMPETITOR_RE.test(text)
}

export function isMarketShareResponse(response: Pick<ChatResponse, 'tool_calls' | 'chart'>): boolean {
  if (response.tool_calls.includes('get_market_share')) return true
  return response.chart?.source_tool === 'get_market_share'
}

export function isMarketShareChart(chart: ChartPayload): boolean {
  return chart.source_tool === 'get_market_share'
}

export function resolveResponseDateRange(
  sources: SourceMeta[],
  fallback?: DateRange,
): DateRange | null {
  const ranges = sources
    .map(s => s.date_range)
    .filter((r): r is DateRange => Boolean(r?.start && r?.end))

  if (ranges.length === 0) {
    return fallback?.start && fallback?.end ? fallback : null
  }

  return {
    start: ranges.reduce((min, r) => (r.start < min ? r.start : min), ranges[0].start),
    end: ranges.reduce((max, r) => (r.end > max ? r.end : max), ranges[0].end),
  }
}

export function formatSourcePeriod({ start, end }: DateRange): string {
  const startDate = new Date(`${start}T12:00:00`)
  const endDate = new Date(`${end}T12:00:00`)
  const startLabel = startDate.toLocaleDateString('sv-SE', { day: 'numeric', month: 'long' })
  const endLabel = endDate.toLocaleDateString('sv-SE', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
  return `${startLabel}–${endLabel}`
}

export function formatSharePct(value: number): string {
  return `${value.toLocaleString('sv-SE', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })} %`
}

export function marketShareLegendItems(
  chart: ChartPayload,
  supplierName?: string,
): { supplierLabel: string; supplierPct: number; othersPct: number } | null {
  if (!isMarketShareChart(chart)) return null

  const ossRow = chart.data.find(row => row.name === 'Oss')
  const compRow = chart.data.find(row => row.name === 'Konkurrenter')
  const ossRev = Number(ossRow?.[chart.y_key] ?? 0)
  const compRev = Number(compRow?.[chart.y_key] ?? 0)
  const total = ossRev + compRev
  if (total <= 0) return null

  return {
    supplierLabel: supplierName || 'Er leverantör',
    supplierPct: (ossRev / total) * 100,
    othersPct: (compRev / total) * 100,
  }
}

export function visibleResponseLimitations(
  limitations: string[],
  response: Pick<ChatResponse, 'tool_calls' | 'chart'>,
): string[] {
  if (!isMarketShareResponse(response)) return limitations
  return limitations.filter(l => !isAggregateCompetitorLimitation(l))
}
