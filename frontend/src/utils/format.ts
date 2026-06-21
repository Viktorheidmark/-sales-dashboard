export function formatSEK(value: number | null | undefined): string {
  if (value == null) return '—'
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M kr`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k kr`
  return `${value.toFixed(0)} kr`
}

export function formatNumber(value: number | null | undefined): string {
  if (value == null) return '—'
  return value.toLocaleString('sv-SE')
}

export function formatPct(value: number | null | undefined): string {
  if (value == null) return '—'
  return `${value.toFixed(1)}%`
}

export function formatPctChange(value: number | null | undefined): string {
  if (value == null) return '—'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}%`
}

export function formatPeriod(period: string, granularity: string): string {
  const d = new Date(period + 'T00:00:00')
  if (granularity === 'day') {
    return d.toLocaleDateString('sv-SE', { month: 'short', day: 'numeric' })
  }
  if (granularity === 'week') {
    return `W${getISOWeek(d)} ${d.getFullYear()}`
  }
  return d.toLocaleDateString('sv-SE', { month: 'short', year: 'numeric' })
}

function getISOWeek(d: Date): number {
  const tmp = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  tmp.setDate(tmp.getDate() + 4 - (tmp.getDay() || 7))
  const yearStart = new Date(tmp.getFullYear(), 0, 1)
  return Math.ceil(((tmp.getTime() - yearStart.getTime()) / 86400000 + 1) / 7)
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('sv-SE', {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

/** ISO date string for N days ago */
export function daysAgo(n: number): string {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}

export function today(): string {
  return new Date().toISOString().slice(0, 10)
}
