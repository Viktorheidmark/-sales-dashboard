import type { OverviewResponse } from '../../api/types'

interface DataStatusRowProps {
  data: OverviewResponse | null
  loading: boolean
}

function formatPeriodLabel(start: string, end: string): string {
  const s = new Date(start + 'T12:00:00')
  const e = new Date(end + 'T12:00:00')
  const sameYear = s.getFullYear() === e.getFullYear()
  const startStr = s.toLocaleDateString('sv-SE', {
    day: 'numeric',
    month: 'long',
    ...(sameYear ? {} : { year: 'numeric' }),
  })
  const endStr = e.toLocaleDateString('sv-SE', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
  return `${startStr}–${endStr}`
}

function formatShortDate(iso: string): string {
  return new Date(iso + 'T12:00:00').toLocaleDateString('sv-SE', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

function formatShortDatetime(iso: string): string {
  const d = new Date(iso)
  const date = d.toLocaleDateString('sv-SE', { day: 'numeric', month: 'long', year: 'numeric' })
  const time = d.toLocaleTimeString('sv-SE', { hour: '2-digit', minute: '2-digit' })
  return `${date} ${time}`
}

function num(n: number): string {
  return n.toLocaleString('sv-SE')
}

export function DataStatusRow({ data, loading }: DataStatusRowProps) {
  if (loading || !data) return null

  const period = formatPeriodLabel(data.date_range.start, data.date_range.end)

  return (
    <div className="-mt-3 px-1 space-y-0.5">
      <p className="text-xs text-zinc-500">
        <span className="font-medium text-zinc-600">Dataperiod:</span>{' '}
        {period} · {num(data.total_orders)} ordrar · {num(data.total_units)} sålda enheter
      </p>
      {(data.latest_order_date || data.generated_at) && (
        <p className="text-xs text-zinc-400">
          {data.latest_order_date && (
            <>Senast transaktionsdatum: {formatShortDate(data.latest_order_date)}</>
          )}
          {data.latest_order_date && data.generated_at && ' · '}
          {data.generated_at && <>Beräknad: {formatShortDatetime(data.generated_at)}</>}
        </p>
      )}
    </div>
  )
}
