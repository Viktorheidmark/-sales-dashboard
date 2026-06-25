import type { AuthUser } from '../../api/types'
import { DATE_PRESETS, type DatePreset } from '../../utils/dateRange'

interface OverviewHeroProps {
  user: AuthUser
  datePreset: DatePreset
  onDatePresetChange: (preset: DatePreset) => void
  onRefresh: () => void
  anyLoading: boolean
  latestOrderDate?: string | null
  generatedAt?: string
}

function formatShortDate(iso: string): string {
  return new Date(iso + 'T12:00:00').toLocaleDateString('sv-SE', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
}

export function OverviewHero({
  user,
  datePreset,
  onDatePresetChange,
  onRefresh,
  anyLoading,
  latestOrderDate,
  generatedAt,
}: OverviewHeroProps) {
  return (
    <header className="overview-hero-zone">
      <div className="overview-hero-atmosphere" aria-hidden />

      <div className="overview-hero-content">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="overview-hero-heading min-w-0 flex-1">
            <p className="overview-hero-eyebrow">Solvigo Sales Intelligence</p>
            <h1 className="overview-hero-title">Försäljningsöversikt</h1>
            <p className="overview-hero-subtitle">
              AI-driven analys av försäljning, produkter och regional utveckling.
            </p>
            <div className="overview-hero-meta">
              <span className="overview-hero-supplier">{user.supplier_name}</span>
              <span className="overview-hero-dot" aria-hidden>·</span>
              <span className="overview-hero-tag">Leverantörsvy</span>
              {latestOrderDate && (
                <>
                  <span className="overview-hero-dot" aria-hidden>·</span>
                  <span className="overview-hero-date">
                    Data t.o.m. {formatShortDate(latestOrderDate)}
                  </span>
                </>
              )}
            </div>
          </div>

          <div className="overview-hero-controls shrink-0 w-full xl:w-auto">
            {generatedAt && (
              <p className="overview-hero-updated xl:text-right mb-2">
                Uppdaterad: {formatShortDate(generatedAt.slice(0, 10))}
              </p>
            )}
            <div className="flex flex-col sm:flex-row flex-wrap items-stretch sm:items-center gap-2.5">
              <div className="period-pill-control" role="group" aria-label="Välj period">
                {DATE_PRESETS.map(p => (
                  <button
                    key={p.value}
                    type="button"
                    onClick={() => onDatePresetChange(p.value)}
                    className={`period-pill${datePreset === p.value ? ' period-pill-active' : ''}`}
                    aria-pressed={datePreset === p.value}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              <button
                type="button"
                onClick={onRefresh}
                disabled={anyLoading}
                className="btn-refresh-premium"
                aria-label="Uppdatera"
              >
                <span className={anyLoading ? 'animate-spin inline-block' : 'inline-block'} aria-hidden>↻</span>
                Uppdatera
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}
