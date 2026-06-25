import type { InsightSummary, InsightDetail } from '../api/types'
import { toolLabelSv } from './sourcePresentation'

const INSIGHT_CHIP_LABELS: Record<string, string> = {
  get_sales_over_time: 'Trendanalys',
  get_top_products: 'Produkter',
  get_sales_by_region: 'Regioner',
  get_market_share: 'Marknadsandel',
  get_declining_products: 'Produkter',
  get_overview: 'Försäljning',
  get_supplier_kpis: 'Försäljning',
  get_revenue_drivers: 'Försäljning',
}

export function insightCountLabel(count: number): string {
  if (count === 1) return '1 sparad insikt'
  return `${count} sparade insikter`
}

export function insightChipLabels(summary: Pick<InsightSummary, 'source_tools' | 'has_chart'>): string[] {
  const chips: string[] = []

  for (const tool of summary.source_tools) {
    const label = INSIGHT_CHIP_LABELS[tool] ?? toolLabelSv(tool)
    if (!chips.includes(label)) {
      chips.push(label)
    }
  }

  if (summary.has_chart && !chips.includes('Diagram')) {
    chips.push('Diagram')
  }

  return chips.slice(0, 3)
}

export function formatInsightDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('sv-SE', { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return iso
  }
}

const KNOWN_STABILITY_NOTES = new Set([
  'Försäljningen var relativt stabil under perioden',
])

/** Only surface stability notes that read as intentional user-facing copy. */
export function userFacingStabilityNote(note?: string | null): string | null {
  if (!note) return null
  const trimmed = note.trim()
  if (KNOWN_STABILITY_NOTES.has(trimmed)) return trimmed
  if (/^Försäljningen\s/i.test(trimmed) && trimmed.length <= 120) return trimmed
  return null
}

export function insightDetailChipLabels(
  detail: Pick<InsightDetail, 'tool_calls' | 'chart'>,
): string[] {
  return insightChipLabels({
    source_tools: detail.tool_calls,
    has_chart: Boolean(detail.chart),
  })
}

/** Hide raw axis keys and malformed highlight labels in saved insight previews. */
export function formatHighlightPeriodLabel(label: string, display?: string): string | null {
  const candidate = (display ?? label).trim()
  if (!candidate) return null
  if (/^get_/i.test(candidate) || /^v\d+$/i.test(candidate)) return null

  if (/^\d{4}-\d{2}(-\d{2})?$/.test(candidate)) {
    try {
      const iso = candidate.length === 7 ? `${candidate}-01` : candidate
      const d = new Date(`${iso}T12:00:00`)
      if (!Number.isNaN(d.getTime())) {
        return candidate.length === 7
          ? d.toLocaleDateString('sv-SE', { month: 'short', year: 'numeric' })
          : d.toLocaleDateString('sv-SE', { day: 'numeric', month: 'short', year: 'numeric' })
      }
    } catch {
      return null
    }
  }

  if (/^W\d+\s+\d{4}$/i.test(candidate)) return candidate

  if (/^\d{1,2}\s+[a-zåäö]+/i.test(candidate)) return candidate

  const monthMatch = /^(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec)/i.test(candidate)
  if (monthMatch) return candidate

  const words = candidate.split(/\s+/).filter(Boolean)
  if (words.length <= 2 && words.every(w => w.length < 9) && !monthMatch && !/^\d/.test(candidate)) {
    return null
  }

  if (/[a-zåäö]{4,}/i.test(candidate) && candidate.includes(' ')) {
    return candidate
  }

  return null
}

export function minorVariationLabel(changePct: number | undefined): string | null {
  if (changePct == null || Number.isNaN(changePct)) return null
  if (Math.abs(changePct) < 5) return 'Mindre avvikelse'
  return null
}
