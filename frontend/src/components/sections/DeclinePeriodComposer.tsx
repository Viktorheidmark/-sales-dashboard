import { useState, useEffect } from 'react'
import { useTenantBranding } from '../../context/TenantBrandingContext'
import { api } from '../../api/client'

export type DeclinePeriodKind =
  | 'rolling_30'
  | 'rolling_90'
  | 'year_to_date'
  | 'full_history'
  | 'custom'

interface PeriodRange {
  start: string
  end: string
}

interface Props {
  locked?: boolean
  lockedKind?: DeclinePeriodKind
  lockedRange?: PeriodRange
  onSubmit: (periodKind: DeclinePeriodKind, customRange?: PeriodRange) => void
}

const OPTIONS: { kind: DeclinePeriodKind; label: string }[] = [
  { kind: 'rolling_30', label: 'Senaste 30 dagarna' },
  { kind: 'rolling_90', label: 'Senaste 90 dagarna' },
  { kind: 'year_to_date', label: 'I år' },
  { kind: 'full_history', label: 'Sedan start' },
  { kind: 'custom', label: 'Anpassad period' },
]

function svDate(iso: string): string {
  if (!iso) return ''
  try {
    return new Date(iso + 'T00:00:00').toLocaleDateString('sv-SE', {
      day: 'numeric', month: 'short', year: 'numeric',
    })
  } catch {
    return iso
  }
}

function validateCustom(range: PeriodRange, dataMin: string, dataMax: string): string | null {
  if (!range.start || !range.end) {
    return 'Välj start- och slutdatum för perioden.'
  }
  if (range.start > range.end) {
    return 'Startdatum måste vara före slutdatum.'
  }
  if (dataMin && range.start < dataMin) {
    return `Startdatum är innan tillgänglig data (från ${svDate(dataMin)}).`
  }
  if (dataMax && range.end > dataMax) {
    return `Slutdatum är efter tillgänglig data (till ${svDate(dataMax)}).`
  }
  return null
}

export default function DeclinePeriodComposer({
  locked,
  lockedKind,
  lockedRange,
  onSubmit,
}: Props) {
  const { chartPrimary } = useTenantBranding()
  const [selected, setSelected] = useState<DeclinePeriodKind | null>(lockedKind ?? null)
  const [customRange, setCustomRange] = useState<PeriodRange>(lockedRange ?? { start: '', end: '' })
  const [dataMin, setDataMin] = useState('')
  const [dataMax, setDataMax] = useState('')
  const [touched, setTouched] = useState(false)

  useEffect(() => {
    api.getDataStatus().then(s => {
      if (s.period_start) setDataMin(s.period_start.slice(0, 10))
      if (s.period_end) setDataMax(s.period_end.slice(0, 10))
    }).catch(() => {})
  }, [])

  const customError = selected === 'custom' && touched
    ? validateCustom(customRange, dataMin, dataMax)
    : null

  const isValid = selected !== null && (
    selected !== 'custom' || validateCustom(customRange, dataMin, dataMax) === null
  )

  const handleSubmit = () => {
    setTouched(true)
    if (!selected || !isValid) return
    if (selected === 'custom') {
      onSubmit('custom', customRange)
    } else {
      onSubmit(selected)
    }
  }

  if (locked && lockedKind) {
    const label = OPTIONS.find(o => o.kind === lockedKind)?.label ?? lockedKind
    return (
      <div className="rounded-xl border border-workspace-border bg-workspace-surface/50 px-4 py-3 text-sm text-workspace-text-muted flex flex-wrap items-center gap-2">
        <span className="font-medium text-workspace-text">Analysera produktnedgång:</span>
        <span
          className="px-2 py-0.5 rounded border text-white text-xs"
          style={{ background: chartPrimary, borderColor: chartPrimary }}
        >
          {label}
          {lockedKind === 'custom' && lockedRange?.start && lockedRange?.end && (
            <> · {svDate(lockedRange.start)} – {svDate(lockedRange.end)}</>
          )}
        </span>
      </div>
    )
  }

  return (
    <div className="rounded-2xl border border-workspace-border bg-workspace-surface shadow-sm overflow-hidden">
      <div className="px-5 pt-5 pb-3 border-b border-workspace-border">
        <p className="text-sm font-semibold text-workspace-text">Analysera produktnedgång</p>
        <p className="text-xs text-workspace-text-muted mt-0.5">
          Välj vilken period du vill analysera för att se vilken produkt som tappat mest.
        </p>
      </div>

      <div className="px-5 pt-4 pb-2 grid grid-cols-1 sm:grid-cols-2 gap-2">
        {OPTIONS.map(({ kind, label }) => {
          const active = selected === kind
          return (
            <button
              key={kind}
              type="button"
              onClick={() => {
                setSelected(kind)
                setTouched(false)
              }}
              disabled={!!locked}
              className={[
                'text-left px-4 py-3 rounded-xl border text-sm font-medium transition-colors',
                active
                  ? 'text-white border-transparent'
                  : 'border-workspace-border bg-workspace-surface text-workspace-text hover:border-workspace-text-muted',
              ].join(' ')}
              style={active ? { background: chartPrimary, borderColor: chartPrimary } : {}}
            >
              {label}
            </button>
          )
        })}
      </div>

      {selected === 'custom' && (
        <div className="px-5 pb-4 pt-2">
          <div
            className="rounded-xl border p-4 space-y-3"
            style={{
              borderColor: customRange.start && customRange.end ? chartPrimary + '55' : undefined,
              background: customRange.start && customRange.end ? chartPrimary + '08' : undefined,
            }}
          >
            <span className="block text-xs font-semibold" style={{ color: chartPrimary }}>
              Anpassad period
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <label className="block">
                <span className="text-xs text-workspace-text-muted mb-1 block">Från</span>
                <input
                  type="date"
                  value={customRange.start}
                  min={dataMin || undefined}
                  max={customRange.end || dataMax || undefined}
                  disabled={!!locked}
                  onChange={e => {
                    setCustomRange(prev => ({ ...prev, start: e.target.value }))
                    setTouched(false)
                  }}
                  className="w-full rounded-lg border border-workspace-border bg-workspace-surface px-3 py-1.5 text-sm text-workspace-text focus:outline-none focus:ring-2 disabled:opacity-50"
                  style={{ accentColor: chartPrimary, colorScheme: 'auto' } as React.CSSProperties}
                />
              </label>
              <label className="block">
                <span className="text-xs text-workspace-text-muted mb-1 block">Till</span>
                <input
                  type="date"
                  value={customRange.end}
                  min={customRange.start || dataMin || undefined}
                  max={dataMax || undefined}
                  disabled={!!locked}
                  onChange={e => {
                    setCustomRange(prev => ({ ...prev, end: e.target.value }))
                    setTouched(false)
                  }}
                  className="w-full rounded-lg border border-workspace-border bg-workspace-surface px-3 py-1.5 text-sm text-workspace-text focus:outline-none focus:ring-2 disabled:opacity-50"
                  style={{ accentColor: chartPrimary, colorScheme: 'auto' } as React.CSSProperties}
                />
              </label>
            </div>
            {customRange.start && customRange.end && (
              <p className="text-xs font-medium" style={{ color: chartPrimary }}>
                {svDate(customRange.start)} – {svDate(customRange.end)}
              </p>
            )}
          </div>
        </div>
      )}

      <div className="px-5 pb-5 space-y-3">
        {customError && (
          <p className="text-xs text-workspace-text-muted font-medium">{customError}</p>
        )}
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!!locked || (touched && !isValid) || !selected}
          className="w-full py-2.5 rounded-xl text-sm font-semibold text-white transition-opacity disabled:opacity-40"
          style={{ background: chartPrimary }}
        >
          Analysera nedgång
        </button>
      </div>
    </div>
  )
}
