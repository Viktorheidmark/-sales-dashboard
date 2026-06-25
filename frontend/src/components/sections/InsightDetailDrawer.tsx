import type { InsightDetail } from '../../api/types'
import { MiniAssistantChart } from '../charts/MiniAssistantChart'
import {
  formatInsightDate,
  insightDetailChipLabels,
  minorVariationLabel,
  userFacingStabilityNote,
} from '../../utils/insightPresentation'

interface InsightDetailDrawerProps {
  detail: InsightDetail | null
  loading: boolean
  pdfLoading: string | null
  deleteConfirm: string | null
  exportError: string | null
  onClose: () => void
  onExportPdf: (id: string, createdAt: string) => void
  onDeleteRequest: (id: string) => void
  onDeleteConfirm: (id: string) => void
  onDeleteCancel: () => void
}

export function InsightDetailDrawer({
  detail,
  loading,
  pdfLoading,
  deleteConfirm,
  exportError,
  onClose,
  onExportPdf,
  onDeleteRequest,
  onDeleteConfirm,
  onDeleteCancel,
}: InsightDetailDrawerProps) {
  const chips = detail ? insightDetailChipLabels(detail) : []
  const stabilityNote = detail?.chart ? userFacingStabilityNote(detail.chart.stability_note) : null
  const variationLabel = detail?.chart?.highlights
    ? minorVariationLabel(detail.chart.highlights.change_pct)
    : null

  return (
    <div className="insight-drawer-root fixed inset-0 z-50 flex">
      <div
        className="insight-drawer-overlay absolute inset-0"
        onClick={onClose}
        aria-hidden
      />
      <aside
        className="insight-drawer-panel relative ml-auto h-full w-full flex flex-col"
        aria-labelledby="insight-drawer-title"
      >
        <header className="insight-drawer-header shrink-0">
          <h2 id="insight-drawer-title" className="insight-drawer-title">Insiktsdetaljer</h2>
          <button
            type="button"
            onClick={onClose}
            className="insight-drawer-close"
            aria-label="Stäng"
          >
            ✕
          </button>
        </header>

        <div className="insight-drawer-body flex-1 overflow-y-auto scrollbar-thin">
          {loading || !detail ? (
            <div className="flex justify-center items-center h-40">
              <div className="insight-drawer-spinner" aria-label="Laddar" />
            </div>
          ) : (
            <div className="insight-drawer-content">
              <div className="insight-drawer-intro">
                <time className="insight-drawer-date" dateTime={detail.created_at}>
                  {formatInsightDate(detail.created_at)}
                </time>
                <h3 className="insight-drawer-question">{detail.question}</h3>
              </div>

              <div className="insight-drawer-summary">
                <p className="insight-drawer-answer whitespace-pre-wrap">{detail.answer}</p>
              </div>

              {detail.chart && (
                <div className="insight-drawer-chart-card">
                  {detail.chart.title && (
                    <h4 className="insight-drawer-chart-title">{detail.chart.title}</h4>
                  )}
                  {detail.chart.description && (
                    <p className="insight-drawer-chart-desc">{detail.chart.description}</p>
                  )}
                  <div className="insight-drawer-chart-area">
                    <MiniAssistantChart
                      chart={detail.chart}
                      expanded
                      tenantColors
                      sanitizeHighlightLabels
                      highlightsLayout="two-column"
                    />
                  </div>
                  {stabilityNote && (
                    <p className="insight-drawer-chart-note">{stabilityNote}</p>
                  )}
                </div>
              )}

              {(chips.length > 0 || variationLabel) && (
                <div className="insight-drawer-labels">
                  {chips.map(chip => (
                    <span key={chip} className="insight-library-chip">{chip}</span>
                  ))}
                  {variationLabel && !chips.includes(variationLabel) && (
                    <span className="insight-library-chip">{variationLabel}</span>
                  )}
                </div>
              )}

              {detail.limitations.length > 0 && (
                <div className="insight-drawer-limitations">
                  {detail.limitations.map((l, i) => (
                    <p key={i} className="insight-drawer-limitation">⚠ {l}</p>
                  ))}
                </div>
              )}

              {exportError && (
                <p className="insight-drawer-export-error">{exportError}</p>
              )}

              <div className="insight-drawer-actions">
                <button
                  type="button"
                  onClick={() => onExportPdf(detail.id, detail.created_at)}
                  disabled={pdfLoading === detail.id}
                  className="insight-drawer-btn insight-drawer-btn-primary"
                >
                  {pdfLoading === detail.id ? 'Genererar rapport…' : 'Exportera rapport som PDF'}
                </button>

                {deleteConfirm === detail.id ? (
                  <div className="insight-drawer-delete-confirm">
                    <span className="text-xs text-theme-muted">Bekräfta borttagning?</span>
                    <button
                      type="button"
                      className="insight-drawer-btn insight-drawer-btn-danger-solid"
                      onClick={() => onDeleteConfirm(detail.id)}
                    >
                      Ta bort
                    </button>
                    <button
                      type="button"
                      className="insight-drawer-btn insight-drawer-btn-quiet"
                      onClick={onDeleteCancel}
                    >
                      Avbryt
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => onDeleteRequest(detail.id)}
                    className="insight-drawer-btn insight-drawer-btn-danger"
                  >
                    Ta bort insikt
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </aside>
    </div>
  )
}
