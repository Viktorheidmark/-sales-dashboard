import type { ChartPayload } from '../api/types'

/**
 * Stable identity for a chart payload, used as a defensive client-side
 * deduplication key (safety net, not the primary fix for duplicate charts).
 *
 * For canonical analytics-orchestration charts we key on plan identity:
 * analysis_plan_id + intent + Period A + Period B + chart type. For other
 * charts we fall back to a conservative content key so only *exact* duplicates
 * collapse — distinct charts are never merged.
 */
export function chartIdentity(chart: ChartPayload): string {
  if (chart.analysis_plan_id) {
    const a = chart.period_a ? `${chart.period_a.start}_${chart.period_a.end}` : ''
    const b = chart.period_b ? `${chart.period_b.start}_${chart.period_b.end}` : ''
    return [
      'plan',
      chart.analysis_plan_id,
      chart.intent ?? '',
      a,
      b,
      chart.chart_type,
    ].join('|')
  }
  return [
    'content',
    chart.chart_type,
    chart.chart_variant ?? '',
    chart.title ?? '',
    chart.source_tool ?? '',
    String(chart.data?.length ?? 0),
  ].join('|')
}

/**
 * Return charts in original order with duplicate identities removed.
 * A null/undefined entry is dropped.
 */
export function dedupeCharts(charts: (ChartPayload | null | undefined)[]): ChartPayload[] {
  const seen = new Set<string>()
  const out: ChartPayload[] = []
  for (const chart of charts) {
    if (!chart) continue
    const id = chartIdentity(chart)
    if (seen.has(id)) continue
    seen.add(id)
    out.push(chart)
  }
  return out
}

/** Two-bar period comparison result (legacy decline_comparison + orchestrated period_comparison). */
export function isPeriodComparisonChart(chart: ChartPayload | null | undefined): boolean {
  return chart?.chart_variant === 'period_comparison' || chart?.chart_variant === 'decline_comparison'
}
