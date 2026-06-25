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

export function resolveDeclineComparisonLabel(sources: SourceMeta[]): string | null {
  const declining = sources.find(s => s.tool === 'get_declining_products')
  return declining?.comparison_period_label ?? null
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

export function resolveSourceSummaryLine(
  sources: SourceMeta[],
  fallback?: DateRange,
): string | null {
  const declineComparison = resolveDeclineComparisonLabel(sources)
  if (declineComparison) {
    const label = declineComparison.startsWith('Jämförelse:')
      ? declineComparison
      : `Jämförelse: ${declineComparison}`
    return `Data: Försäljningsdata · ${label}`
  }
  const dateRange = resolveResponseDateRange(sources, fallback)
  if (!dateRange) return null
  return `Data: Försäljningsdata · ${formatSourcePeriod(dateRange)}`
}

function parseLocalDate(iso: string): Date {
  return new Date(`${iso.slice(0, 10)}T12:00:00`)
}

/** Swedish readable range — year on both ends when the range crosses calendar years. */
export function formatSourcePeriod({ start, end }: DateRange): string {
  const startDate = parseLocalDate(start)
  const endDate = parseLocalDate(end)
  const startYear = startDate.getFullYear()
  const endYear = endDate.getFullYear()
  const startMonth = startDate.getMonth()
  const endMonth = endDate.getMonth()

  const monthLong = (d: Date) => d.toLocaleDateString('sv-SE', { month: 'long' })
  const day = (d: Date) => d.getDate()

  if (startYear === endYear && startMonth === endMonth) {
    return `${day(startDate)}–${day(endDate)} ${monthLong(endDate)} ${endYear}`
  }
  if (startYear === endYear) {
    return `${day(startDate)} ${monthLong(startDate)}–${day(endDate)} ${monthLong(endDate)} ${endYear}`
  }
  return `${day(startDate)} ${monthLong(startDate)} ${startYear}–${day(endDate)} ${monthLong(endDate)} ${endYear}`
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

const INCOMPLETE_PERIOD_RE =
  /ofullständig|exkluderats|pågående\s+(vecka|månad|dag)|pågående\s+\w+\s+är|finns i serien|jämförelseperiod/i

const COMPLETED_WEEK_ANSWER_RE = /senaste avslutade vecka/i

export function isIncompletePeriodLimitation(text: string): boolean {
  return INCOMPLETE_PERIOD_RE.test(text)
}

export function visibleResponseLimitations(
  limitations: string[],
  response: Pick<ChatResponse, 'tool_calls' | 'chart' | 'answer'>,
): string[] {
  let filtered = limitations
  if (isMarketShareResponse(response)) {
    filtered = filtered.filter(l => !isAggregateCompetitorLimitation(l))
  }
  if (response.chart?.period_note || COMPLETED_WEEK_ANSWER_RE.test(response.answer ?? '')) {
    filtered = filtered.filter(l => !isIncompletePeriodLimitation(l))
  }
  return filtered
}

const CONVERSATIONAL_QUESTION_RE =
  /^(hej|hejsan|hallå|tack|okej|ok|bra|toppen|perfekt|kul)\b|vad kan du (hjälpa|göra)|hur kan du hjälpa/i

const MISSING_DATA_ANSWER_RE =
  /lagerdata|inte den typen av data|finns inte i datakällan|utanför vad jag kan|aggregerad form|det är inte tillåtet/i

export function isPlainConversationalResponse(
  response: Pick<ChatResponse, 'tool_calls' | 'chart' | 'deep_dive' | 'response_kind' | 'analysis_context'>,
  question?: string,
): boolean {
  if (response.tool_calls.length > 0) return false
  if (response.chart || response.deep_dive) return false
  if (response.response_kind === 'conversational') return true
  if (response.response_kind === 'insufficient_data' || response.response_kind === 'unsupported') return false
  if (response.analysis_context?.awaiting_decline_period) return true
  if (question && CONVERSATIONAL_QUESTION_RE.test(question.trim())) return true
  return false
}

export function isCompactMissingDataResponse(
  response: Pick<ChatResponse, 'tool_calls' | 'response_kind' | 'answer' | 'limitations'>,
): boolean {
  if (response.tool_calls.length > 0) return false
  if (response.response_kind === 'insufficient_data' || response.response_kind === 'unsupported') {
    return true
  }
  if (response.response_kind === 'conversational') return false
  if (MISSING_DATA_ANSWER_RE.test(response.answer ?? '')) return true
  return response.limitations.some(l =>
    /finns inte i datakällan|säkerhetsskäl|aggregerat/i.test(l),
  )
}
