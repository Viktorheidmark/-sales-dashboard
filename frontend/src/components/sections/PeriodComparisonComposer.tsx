import { useState, useEffect } from 'react'
import { useTenantBranding } from '../../context/TenantBrandingContext'
import { api } from '../../api/client'

interface PeriodRange {
  start: string
  end: string
}

type ComparisonMode = 'custom'

interface Props {
  locked?: boolean
  lockedDates?: { periodA: PeriodRange; periodB: PeriodRange }
  onSubmit: (periodA: PeriodRange, periodB: PeriodRange, mode: ComparisonMode) => void
}

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

function validate(
  a: PeriodRange,
  b: PeriodRange,
  dataMin: string,
  dataMax: string,
): string | null {
  if (!a.start || !a.end || !b.start || !b.end) {
    return 'Välj start- och slutdatum för båda perioderna.'
  }
  if (a.start > a.end) return 'Jämförelseperiod: startdatum måste vara före slutdatum.'
  if (b.start > b.end) return 'Analyserad period: startdatum måste vara före slutdatum.'
  if (a.start <= b.end && b.start <= a.end) {
    return 'Perioderna får inte överlappa. Välj separata intervall.'
  }
  if (dataMin && (a.start < dataMin || b.start < dataMin)) {
    return `Startdatum är innan tillgänglig data (från ${svDate(dataMin)}).`
  }
  if (dataMax && (a.end > dataMax || b.end > dataMax)) {
    return `Slutdatum är efter tillgänglig data (till ${svDate(dataMax)}).`
  }
  return null
}

export default function PeriodComparisonComposer({ locked, lockedDates, onSubmit }: Props) {
  const { chartPrimary } = useTenantBranding()
  const [periodA, setPeriodA] = useState<PeriodRange>(lockedDates?.periodA ?? { start: '', end: '' })
  const [periodB, setPeriodB] = useState<PeriodRange>(lockedDates?.periodB ?? { start: '', end: '' })
  const [dataMin, setDataMin] = useState('')
  const [dataMax, setDataMax] = useState('')
  const [touched, setTouched] = useState(false)

  useEffect(() => {
    api.getDataStatus().then(s => {
      if (s.period_start) setDataMin(s.period_start.slice(0, 10))
      if (s.period_end) setDataMax(s.period_end.slice(0, 10))
    }).catch(() => {})
  }, [])

  const error = touched ? validate(periodA, periodB, dataMin, dataMax) : null
  const isValid = validate(periodA, periodB, dataMin, dataMax) === null

  const handleSubmit = () => {
    setTouched(true)
    if (!isValid) return
    onSubmit(periodA, periodB, 'custom')
  }

  const handleDateChange = (
    panel: 'a' | 'b',
    field: 'start' | 'end',
    value: string,
  ) => {
    setTouched(false)
    if (panel === 'a') setPeriodA(prev => ({ ...prev, [field]: value }))
    else setPeriodB(prev => ({ ...prev, [field]: value }))
  }

  if (locked && lockedDates) {
    return (
      <div className="rounded-xl border border-workspace-border bg-workspace-surface/50 px-4 py-3 text-sm text-workspace-text-muted flex flex-wrap items-center gap-2">
        <span className="font-medium text-workspace-text">Jämför perioder:</span>
        <span className="px-2 py-0.5 rounded bg-workspace-surface border border-workspace-border text-workspace-text text-xs">
          {svDate(lockedDates.periodA.start)} – {svDate(lockedDates.periodA.end)}
        </span>
        <span className="text-xs opacity-50">vs</span>
        <span
          className="px-2 py-0.5 rounded border text-white text-xs"
          style={{ background: chartPrimary, borderColor: chartPrimary }}
        >
          {svDate(lockedDates.periodB.start)} – {svDate(lockedDates.periodB.end)}
        </span>
      </div>
    )
  }

  return (
    <div className="rounded-2xl border border-workspace-border bg-workspace-surface shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-5 pt-5 pb-3 border-b border-workspace-border">
        <p className="text-sm font-semibold text-workspace-text">Jämför perioder</p>
        <p className="text-xs text-workspace-text-muted mt-0.5">
          Välj två datumintervall för att se vad som förändrats i försäljningen.
        </p>
      </div>

      {/* Panels */}
      <div className="px-5 pb-4 pt-4 flex flex-col md:flex-row gap-3 items-stretch">
        {/* Jämförelseperiod (baseline, neutral) */}
        <DatePanel
          label="Jämförelseperiod"
          accentColor="#6b7280"
          period={periodA}
          dataMin={dataMin}
          dataMax={dataMax}
          locked={!!locked}
          onStartChange={v => handleDateChange('a', 'start', v)}
          onEndChange={v => handleDateChange('a', 'end', v)}
        />

        {/* Connector */}
        <div className="flex items-center justify-center shrink-0 text-xs text-workspace-text-muted/50 font-medium px-1 md:py-4">
          vs
        </div>

        {/* Analyserad period (active, tenant color) */}
        <DatePanel
          label="Analyserad period"
          accentColor={chartPrimary}
          period={periodB}
          dataMin={dataMin}
          dataMax={dataMax}
          locked={!!locked}
          onStartChange={v => handleDateChange('b', 'start', v)}
          onEndChange={v => handleDateChange('b', 'end', v)}
        />
      </div>

      {/* Error + submit */}
      <div className="px-5 pb-5 space-y-3">
        {error && (
          <p className="text-xs text-workspace-text-muted font-medium">{error}</p>
        )}
        <button
          onClick={handleSubmit}
          disabled={!!locked || (touched && !isValid)}
          className="w-full py-2.5 rounded-xl text-sm font-semibold text-white transition-opacity disabled:opacity-40"
          style={{ background: chartPrimary }}
        >
          Visa jämförelse
        </button>
      </div>
    </div>
  )
}

interface DatePanelProps {
  label: string
  accentColor: string
  period: PeriodRange
  dataMin: string
  dataMax: string
  locked: boolean
  onStartChange: (v: string) => void
  onEndChange: (v: string) => void
}

function DatePanel({ label, accentColor, period, dataMin, dataMax, locked, onStartChange, onEndChange }: DatePanelProps) {
  const hasDates = period.start && period.end
  const isNeutral = accentColor === '#6b7280'

  return (
    <div
      className="flex-1 rounded-xl border p-4 space-y-3 transition-colors"
      style={{
        borderColor: hasDates
          ? isNeutral ? 'rgba(107,114,128,0.35)' : accentColor + '55'
          : undefined,
        background: hasDates
          ? isNeutral ? 'rgba(107,114,128,0.04)' : accentColor + '08'
          : undefined,
      }}
    >
      <span
        className="block text-xs font-semibold"
        style={{ color: isNeutral ? '#9ca3af' : accentColor }}
      >
        {label}
      </span>

      <div className="space-y-2">
        <label className="block">
          <span className="text-xs text-workspace-text-muted mb-1 block">Från</span>
          <input
            type="date"
            value={period.start}
            min={dataMin || undefined}
            max={period.end || dataMax || undefined}
            disabled={locked}
            onChange={e => onStartChange(e.target.value)}
            className="w-full rounded-lg border border-workspace-border bg-workspace-surface px-3 py-1.5 text-sm text-workspace-text focus:outline-none focus:ring-2 disabled:opacity-50"
            style={{ accentColor, colorScheme: 'auto' } as React.CSSProperties}
          />
        </label>
        <label className="block">
          <span className="text-xs text-workspace-text-muted mb-1 block">Till</span>
          <input
            type="date"
            value={period.end}
            min={period.start || dataMin || undefined}
            max={dataMax || undefined}
            disabled={locked}
            onChange={e => onEndChange(e.target.value)}
            className="w-full rounded-lg border border-workspace-border bg-workspace-surface px-3 py-1.5 text-sm text-workspace-text focus:outline-none focus:ring-2 disabled:opacity-50"
            style={{ accentColor, colorScheme: 'auto' } as React.CSSProperties}
          />
        </label>
      </div>

      {hasDates && (
        <p
          className="text-xs font-medium"
          style={{ color: isNeutral ? '#9ca3af' : accentColor }}
        >
          {svDate(period.start)} – {svDate(period.end)}
        </p>
      )}
    </div>
  )
}
