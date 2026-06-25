import { useEffect, useState, type KeyboardEvent, type MouseEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { InsightDetail, InsightSummary } from '../api/types'
import { InsightDetailDrawer } from '../components/sections/InsightDetailDrawer'
import {
  formatInsightDate,
  insightChipLabels,
  insightCountLabel,
} from '../utils/insightPresentation'

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function stopCardClick(e: MouseEvent) {
  e.stopPropagation()
}

function InsightCardSkeleton() {
  return (
    <div className="insight-library-card insight-library-card-skeleton" aria-hidden>
      <div className="h-4 w-24 rounded bg-workspace-border/50 animate-pulse" />
      <div className="mt-4 h-5 w-4/5 rounded bg-workspace-border/50 animate-pulse" />
      <div className="mt-3 space-y-2">
        <div className="h-3 w-full rounded bg-workspace-border/40 animate-pulse" />
        <div className="h-3 w-full rounded bg-workspace-border/40 animate-pulse" />
        <div className="h-3 w-2/3 rounded bg-workspace-border/40 animate-pulse" />
      </div>
      <div className="mt-4 flex gap-2">
        <div className="h-6 w-16 rounded-full bg-workspace-border/40 animate-pulse" />
        <div className="h-6 w-20 rounded-full bg-workspace-border/40 animate-pulse" />
      </div>
    </div>
  )
}

interface InsightLibraryCardProps {
  summary: InsightSummary
  pdfLoading: string | null
  deleteConfirm: string | null
  onOpen: (id: string) => void
  onExportPdf: (id: string, createdAt: string) => void
  onDeleteRequest: (id: string) => void
  onDeleteConfirm: (id: string) => void
  onDeleteCancel: () => void
}

function InsightLibraryCard({
  summary,
  pdfLoading,
  deleteConfirm,
  onOpen,
  onExportPdf,
  onDeleteRequest,
  onDeleteConfirm,
  onDeleteCancel,
}: InsightLibraryCardProps) {
  const chips = insightChipLabels(summary)

  function handleCardKeyDown(e: KeyboardEvent<HTMLElement>) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onOpen(summary.id)
    }
  }

  return (
    <article
      className="insight-library-card"
      role="button"
      tabIndex={0}
      onClick={() => onOpen(summary.id)}
      onKeyDown={handleCardKeyDown}
      aria-label={`Öppna insikt: ${summary.question}`}
    >
      <div className="insight-library-card-top">
        <span className="insight-library-badge" aria-hidden>
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 3h14a1 1 0 011 1v17l-7-4-7 4V4a1 1 0 011-1z" />
          </svg>
        </span>
        <time className="insight-library-date" dateTime={summary.created_at}>
          {formatInsightDate(summary.created_at)}
        </time>
      </div>

      <h2 className="insight-library-title">{summary.question}</h2>
      <p className="insight-library-preview">{summary.answer_preview}</p>

      {chips.length > 0 && (
        <div className="insight-library-chips">
          {chips.map(chip => (
            <span key={chip} className="insight-library-chip">{chip}</span>
          ))}
        </div>
      )}

      <div className="insight-library-footer">
        <button
          type="button"
          className="insight-library-btn insight-library-btn-primary"
          onClick={e => { stopCardClick(e); onOpen(summary.id) }}
        >
          Öppna insikt
        </button>
        <button
          type="button"
          className="insight-library-btn insight-library-btn-secondary"
          onClick={e => { stopCardClick(e); onExportPdf(summary.id, summary.created_at) }}
          disabled={pdfLoading === summary.id}
        >
          {pdfLoading === summary.id ? 'Genererar…' : 'Exportera PDF'}
        </button>

        {deleteConfirm === summary.id ? (
          <span className="insight-library-delete-confirm" onClick={stopCardClick}>
            <span className="text-xs text-theme-muted">Bekräfta?</span>
            <button
              type="button"
              className="insight-library-btn insight-library-btn-danger"
              onClick={() => onDeleteConfirm(summary.id)}
            >
              Ja
            </button>
            <button
              type="button"
              className="insight-library-btn insight-library-btn-quiet"
              onClick={onDeleteCancel}
            >
              Nej
            </button>
          </span>
        ) : (
          <button
            type="button"
            className="insight-library-btn insight-library-btn-quiet insight-library-btn-delete"
            onClick={e => { stopCardClick(e); onDeleteRequest(summary.id) }}
          >
            Ta bort
          </button>
        )}
      </div>
    </article>
  )
}

export function InsightsPage() {
  const [summaries, setSummaries] = useState<InsightSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [detail, setDetail] = useState<InsightDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const [pdfLoading, setPdfLoading] = useState<string | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)

  useEffect(() => {
    loadList()
  }, [])

  function loadList() {
    setLoading(true)
    setError(null)
    api.listInsights()
      .then(setSummaries)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  function openDetail(id: string) {
    setDetailLoading(true)
    setExportError(null)
    api.getInsight(id)
      .then(setDetail)
      .catch(e => setError(e.message))
      .finally(() => setDetailLoading(false))
  }

  async function handleExportPdf(id: string, createdAt: string) {
    setExportError(null)
    setPdfLoading(id)
    try {
      const blob = await api.exportInsightPdf(id)
      downloadBlob(blob, `solvigo-insight-${createdAt.slice(0, 10)}.pdf`)
    } catch (e) {
      setExportError(e instanceof Error ? e.message : 'PDF-export misslyckades')
    } finally {
      setPdfLoading(null)
    }
  }

  async function handleDelete(id: string) {
    try {
      await api.deleteInsight(id)
      setDeleteConfirm(null)
      if (detail?.id === id) setDetail(null)
      loadList()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Borttagning misslyckades')
    }
  }

  return (
    <div className="overview-page overview-content-stage space-y-6 pb-4">
      <header className="overview-hero-zone">
        <div className="overview-hero-atmosphere" aria-hidden />
        <div className="overview-hero-content">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="overview-hero-heading min-w-0">
              <p className="overview-hero-eyebrow">INSIKTSBIBLIOTEK</p>
              <h1 className="overview-hero-title">Sparade insikter</h1>
              <p className="overview-hero-subtitle">
                Analyser och observationer du har sparat från analysassistenten.
              </p>
            </div>
            {!loading && summaries.length > 0 && (
              <p className="insight-library-count shrink-0">{insightCountLabel(summaries.length)}</p>
            )}
          </div>
        </div>
      </header>

      {error && (
        <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3">{error}</p>
      )}

      {loading ? (
        <div className="insight-library-grid">
          {[...Array(4)].map((_, i) => <InsightCardSkeleton key={i} />)}
        </div>
      ) : summaries.length === 0 ? (
        <div className="insights-empty-wrap">
          <div className="insights-empty-card dashboard-panel">
            <div className="insights-empty-icon" aria-hidden>
              <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 3h14a1 1 0 011 1v17l-7-4-7 4V4a1 1 0 011-1z" />
              </svg>
            </div>
            <p className="insights-empty-title">Inga sparade insikter ännu</p>
            <p className="insights-empty-text">
              Spara ett svar från analysassistenten för att bygga upp ditt insiktsbibliotek.
            </p>
            <Link to="/assistant" className="insights-empty-cta">
              Öppna analysassistenten
              <span aria-hidden>→</span>
            </Link>
          </div>
        </div>
      ) : (
        <div className="insight-library-grid">
          {summaries.map(s => (
            <InsightLibraryCard
              key={s.id}
              summary={s}
              pdfLoading={pdfLoading}
              deleteConfirm={deleteConfirm}
              onOpen={openDetail}
              onExportPdf={handleExportPdf}
              onDeleteRequest={setDeleteConfirm}
              onDeleteConfirm={handleDelete}
              onDeleteCancel={() => setDeleteConfirm(null)}
            />
          ))}
        </div>
      )}

      {(detail || detailLoading) && (
        <InsightDetailDrawer
          detail={detail}
          loading={detailLoading}
          pdfLoading={pdfLoading}
          deleteConfirm={deleteConfirm}
          exportError={exportError}
          onClose={() => setDetail(null)}
          onExportPdf={handleExportPdf}
          onDeleteRequest={setDeleteConfirm}
          onDeleteConfirm={handleDelete}
          onDeleteCancel={() => setDeleteConfirm(null)}
        />
      )}
    </div>
  )
}
