import { useEffect, useState } from 'react'
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { api } from '../../api/client'
import type { ChartPayload, InsightDetail, InsightSummary } from '../../api/types'

interface InsightsPanelProps {
  isOpen: boolean
  onClose: () => void
}

const COLORS = ['#4169e1', '#a5b4fc', '#c7d2fe', '#e0e7ff']

function MiniChart({ chart }: { chart: ChartPayload }) {
  if (chart.chart_type === 'line_chart') {
    return (
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={chart.data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" />
          <XAxis dataKey={chart.x_key} tick={{ fontSize: 10, fill: '#a1a1aa' }} tickLine={false} axisLine={false} />
          <YAxis tick={{ fontSize: 10, fill: '#a1a1aa' }} tickLine={false} axisLine={false} width={48} />
          <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
          <Line type="monotone" dataKey={chart.y_key} stroke="#4169e1" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    )
  }
  if (chart.chart_type === 'bar_chart') {
    return (
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={chart.data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" vertical={false} />
          <XAxis dataKey={chart.x_key} tick={{ fontSize: 10, fill: '#a1a1aa' }} tickLine={false} axisLine={false} />
          <YAxis tick={{ fontSize: 10, fill: '#a1a1aa' }} tickLine={false} axisLine={false} width={48} />
          <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
          <Bar dataKey={chart.y_key} fill="#4169e1" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    )
  }
  if (chart.chart_type === 'pie_chart') {
    return (
      <ResponsiveContainer width="100%" height={160}>
        <PieChart>
          <Pie data={chart.data} dataKey={chart.y_key} nameKey={chart.x_key} cx="50%" cy="50%" outerRadius={64} strokeWidth={0}>
            {chart.data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
          </Pie>
          <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
        </PieChart>
      </ResponsiveContainer>
    )
  }
  return null
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleString('sv-SE', { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return iso
  }
}

export function InsightsPanel({ isOpen, onClose }: InsightsPanelProps) {
  const [summaries, setSummaries] = useState<InsightSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [detail, setDetail] = useState<InsightDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) return
    setDetail(null)
    setError(null)
    setExportError(null)
    setDeleteConfirm(null)
    loadList()
  }, [isOpen])

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
    setDeleteConfirm(null)
    api.getInsight(id)
      .then(setDetail)
      .catch(e => setError(e.message))
      .finally(() => setDetailLoading(false))
  }

  const [pdfLoading, setPdfLoading] = useState(false)

  async function handleExportPdf() {
    if (!detail) return
    setExportError(null)
    setPdfLoading(true)
    try {
      const blob = await api.exportInsightPdf(detail.id)
      const date = detail.created_at.slice(0, 10)
      downloadBlob(blob, `solvigo-insight-${date}.pdf`)
    } catch (e) {
      setExportError(e instanceof Error ? e.message : 'PDF-export misslyckades')
    } finally {
      setPdfLoading(false)
    }
  }

  async function handleDelete(id: string) {
    try {
      await api.deleteInsight(id)
      setDetail(null)
      setDeleteConfirm(null)
      loadList()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Delete failed')
    }
  }

  if (!isOpen) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/30 z-40"
        onClick={onClose}
        aria-hidden
      />

      {/* Drawer */}
      <aside className="fixed right-0 top-0 h-full w-full max-w-md bg-white shadow-2xl z-50 flex flex-col">
        {/* Header */}
        <div className="px-5 py-4 border-b border-zinc-200 flex items-center justify-between shrink-0">
          <h2 className="text-sm font-semibold text-zinc-800">Sparade insikter</h2>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-zinc-700 text-lg leading-none"
            aria-label="Stäng"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto">
          {/* Detail view */}
          {detail ? (
            <div className="p-5 space-y-4">
              <button
                onClick={() => { setDetail(null); setExportError(null); setDeleteConfirm(null) }}
                className="text-xs text-brand-600 hover:underline flex items-center gap-1"
              >
                ← Alla insikter
              </button>

              <div>
                <p className="text-xs text-zinc-400 mb-1">{formatDate(detail.created_at)}</p>
                <h3 className="text-sm font-semibold text-zinc-800 leading-snug">{detail.question}</h3>
              </div>

              <div className="text-sm text-zinc-700 leading-relaxed whitespace-pre-wrap bg-zinc-50 rounded-lg px-4 py-3 border border-zinc-100">
                {detail.answer}
              </div>

              {detail.chart && (
                <div className="border border-zinc-100 rounded-lg px-4 py-3">
                  <p className="text-xs font-semibold text-zinc-700 mb-0.5">{detail.chart.title}</p>
                  {detail.chart.description && (
                    <p className="text-xs text-zinc-400 mb-2">{detail.chart.description}</p>
                  )}
                  <MiniChart chart={detail.chart} />
                </div>
              )}

              {detail.tool_calls.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {detail.tool_calls.map(t => (
                    <span key={t} className="text-xs bg-brand-50 text-brand-600 border border-brand-100 rounded px-1.5 py-0.5">
                      {t.replace('get_', '').replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              )}

              {detail.limitations.length > 0 && (
                <div className="space-y-0.5">
                  {detail.limitations.map((l, i) => (
                    <p key={i} className="text-xs text-amber-600">⚠ {l}</p>
                  ))}
                </div>
              )}

              {exportError && (
                <p className="text-xs text-red-600 bg-red-50 rounded px-3 py-2">{exportError}</p>
              )}

              {/* Actions */}
              <div className="space-y-2 pt-1">
                <button
                  onClick={handleExportPdf}
                  disabled={pdfLoading}
                  className="w-full text-sm px-4 py-2.5 rounded-lg bg-brand-500 hover:bg-brand-600 text-white font-medium transition-colors flex items-center justify-center gap-2 disabled:opacity-60"
                >
                  {pdfLoading ? '… Genererar rapport' : '↓ Exportera rapport som PDF'}
                </button>

                <div className="flex items-center gap-2">
                {deleteConfirm === detail.id ? (
                  <span className="flex items-center gap-1.5 ml-auto">
                    <span className="text-xs text-zinc-500">Säker?</span>
                    <button
                      onClick={() => handleDelete(detail.id)}
                      className="text-xs px-2.5 py-1.5 rounded-lg bg-red-500 text-white hover:bg-red-600 transition-colors"
                    >
                      Ta bort
                    </button>
                    <button
                      onClick={() => setDeleteConfirm(null)}
                      className="text-xs px-2 py-1.5 text-zinc-500 hover:text-zinc-700"
                    >
                      Avbryt
                    </button>
                  </span>
                ) : (
                  <button
                    onClick={() => setDeleteConfirm(detail.id)}
                    className="text-xs px-3 py-1.5 rounded-lg border border-zinc-200 text-zinc-400 hover:border-red-300 hover:text-red-500 hover:bg-red-50 transition-colors ml-auto"
                  >
                    Ta bort
                  </button>
                )}
                </div>
              </div>
            </div>
          ) : detailLoading ? (
            <div className="flex justify-center items-center h-32">
              <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            /* List view */
            <div className="p-4">
              {loading && (
                <div className="flex justify-center py-8">
                  <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
                </div>
              )}
              {error && (
                <p className="text-sm text-red-600 text-center py-4">{error}</p>
              )}
              {!loading && !error && summaries.length === 0 && (
                <p className="text-sm text-zinc-400 text-center py-12">
                  Inga sparade insikter ännu.<br />
                  Spara ett svar från chatten för att börja.
                </p>
              )}
              {!loading && summaries.map(s => (
                <button
                  key={s.id}
                  onClick={() => openDetail(s.id)}
                  className="w-full text-left p-3 rounded-lg hover:bg-zinc-50 border border-transparent hover:border-zinc-200 transition-colors mb-2 group"
                >
                  <div className="flex items-start gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-zinc-800 line-clamp-2 leading-snug">{s.question}</p>
                      <p className="text-xs text-zinc-400 mt-0.5 line-clamp-2 leading-snug">{s.answer_preview}</p>
                      <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                        <span className="text-xs text-zinc-400">{formatDate(s.created_at)}</span>
                        {s.has_chart && (
                          <span className="text-xs bg-brand-50 text-brand-600 border border-brand-100 rounded px-1.5 py-0.5">
                            Graf
                          </span>
                        )}
                        {s.source_tools.slice(0, 2).map(t => (
                          <span key={t} className="text-xs bg-zinc-100 text-zinc-500 rounded px-1.5 py-0.5">
                            {t.replace('get_', '').replace(/_/g, ' ')}
                          </span>
                        ))}
                      </div>
                    </div>
                    <span className="text-zinc-300 group-hover:text-zinc-500 text-sm shrink-0">›</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </aside>
    </>
  )
}
