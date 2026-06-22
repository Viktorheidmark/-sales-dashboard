import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { api } from '../api/client'
import type { ChartPayload, InsightDetail, InsightSummary } from '../api/types'
import { PageHeader } from '../components/layout/PageHeader'

const COLORS = ['#4169e1', '#a5b4fc', '#c7d2fe', '#e0e7ff']

function MiniChart({ chart }: { chart: ChartPayload }) {
  if (chart.chart_type === 'line_chart') {
    return (
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={chart.data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis dataKey={chart.x_key} tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
          <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} width={48} />
          <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
          <Line type="monotone" dataKey={chart.y_key} stroke="#4169e1" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    )
  }
  if (chart.chart_type === 'bar_chart') {
    return (
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={chart.data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
          <XAxis dataKey={chart.x_key} tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
          <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} width={48} />
          <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
          <Bar dataKey={chart.y_key} fill="#4169e1" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    )
  }
  if (chart.chart_type === 'pie_chart') {
    return (
      <ResponsiveContainer width="100%" height={180}>
        <PieChart>
          <Pie data={chart.data} dataKey={chart.y_key} nameKey={chart.x_key} cx="50%" cy="50%" outerRadius={72} strokeWidth={0}>
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

function toolLabel(t: string) {
  return t.replace('get_', '').replace(/_/g, ' ')
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
    <div className="space-y-6">
      <PageHeader
        title="Sparade insikter"
        subtitle="Insikter du sparat från analysassistenten."
      />

      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-4 py-3">{error}</p>
      )}

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-3">
              <div className="h-4 w-3/4 bg-slate-100 rounded animate-pulse" />
              <div className="h-3 w-full bg-slate-100 rounded animate-pulse" />
              <div className="h-3 w-1/2 bg-slate-100 rounded animate-pulse" />
            </div>
          ))}
        </div>
      ) : summaries.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm py-20 px-6 text-center">
          <div className="mx-auto w-14 h-14 rounded-2xl bg-slate-900 flex items-center justify-center mb-5">
            <svg className="w-7 h-7 text-slate-400" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 3h14a1 1 0 011 1v17l-7-4-7 4V4a1 1 0 011-1z" />
            </svg>
          </div>
          <p className="text-base font-semibold text-slate-900">Inga sparade insikter ännu</p>
          <p className="text-sm text-slate-400 mt-1.5 max-w-xs mx-auto">
            Spara ett svar från analysassistenten för att bygga upp ditt insiktsbibliotek.
          </p>
          <Link
            to="/assistant"
            className="mt-5 inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium transition-colors"
          >
            Öppna analysassistenten →
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {summaries.map(s => (
            <div key={s.id} className="bg-white rounded-xl border border-slate-100 shadow-sm p-5 flex flex-col hover:shadow-md transition-shadow">
              <button
                onClick={() => openDetail(s.id)}
                className="text-left"
              >
                <p className="text-sm font-semibold text-slate-900 leading-snug line-clamp-2 hover:text-brand-600 transition-colors">
                  {s.question}
                </p>
              </button>
              <p className="mt-2 text-sm text-slate-500 leading-relaxed line-clamp-2 flex-1">{s.answer_preview}</p>

              <div className="flex items-center gap-1.5 mt-3 flex-wrap">
                <span className="text-xs text-slate-400">{formatDate(s.created_at)}</span>
                {s.has_chart && (
                  <span className="text-xs bg-brand-50 text-brand-600 border border-brand-100 rounded px-1.5 py-0.5">Graf</span>
                )}
                {s.source_tools.slice(0, 2).map(t => (
                  <span key={t} className="text-xs bg-slate-100 text-slate-600 rounded px-1.5 py-0.5">{toolLabel(t)}</span>
                ))}
              </div>

              <div className="flex items-center gap-2 mt-4 pt-3 border-t border-slate-100">
                <button
                  onClick={() => openDetail(s.id)}
                  className="text-xs font-medium text-brand-600 hover:text-brand-700"
                >
                  Öppna
                </button>
                <button
                  onClick={() => handleExportPdf(s.id, s.created_at)}
                  disabled={pdfLoading === s.id}
                  className="text-xs font-medium text-slate-500 hover:text-slate-800 disabled:opacity-60"
                >
                  {pdfLoading === s.id ? 'Genererar…' : 'Exportera PDF'}
                </button>

                {deleteConfirm === s.id ? (
                  <span className="ml-auto flex items-center gap-1.5">
                    <span className="text-xs text-slate-500">Bekräfta?</span>
                    <button
                      onClick={() => handleDelete(s.id)}
                      className="text-xs font-medium px-2 py-1 rounded bg-red-500 text-white hover:bg-red-600"
                    >
                      Ja
                    </button>
                    <button
                      onClick={() => setDeleteConfirm(null)}
                      className="text-xs text-slate-500 hover:text-slate-700"
                    >
                      Nej
                    </button>
                  </span>
                ) : (
                  <button
                    onClick={() => setDeleteConfirm(s.id)}
                    className="ml-auto text-xs font-medium text-slate-400 hover:text-red-500"
                  >
                    Ta bort
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {exportError && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-4 py-3">{exportError}</p>
      )}

      {/* Detail overlay */}
      {(detail || detailLoading) && (
        <div className="fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/30" onClick={() => setDetail(null)} aria-hidden />
          <aside className="relative ml-auto h-full w-full max-w-lg bg-white shadow-2xl flex flex-col">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between shrink-0">
              <h2 className="text-sm font-semibold text-slate-800">Insiktsdetaljer</h2>
              <button
                onClick={() => setDetail(null)}
                className="text-slate-400 hover:text-slate-700 text-lg leading-none"
                aria-label="Stäng"
              >
                ✕
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 scrollbar-thin">
              {detailLoading || !detail ? (
                <div className="flex justify-center items-center h-32">
                  <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : (
                <div className="space-y-5">
                  <div>
                    <p className="text-xs text-slate-400 mb-1">{formatDate(detail.created_at)}</p>
                    <h3 className="text-base font-semibold text-slate-900 leading-snug">{detail.question}</h3>
                  </div>

                  <div className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap bg-slate-50 rounded-lg px-4 py-3 border border-slate-100">
                    {detail.answer}
                  </div>

                  {detail.chart && (
                    <div className="border border-slate-100 rounded-lg px-4 py-3">
                      <p className="text-xs font-semibold text-slate-700 mb-0.5">{detail.chart.title}</p>
                      {detail.chart.description && (
                        <p className="text-xs text-slate-400 mb-2">{detail.chart.description}</p>
                      )}
                      <MiniChart chart={detail.chart} />
                    </div>
                  )}

                  {detail.tool_calls.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {detail.tool_calls.map(t => (
                        <span key={t} className="text-xs bg-brand-50 text-brand-600 border border-brand-100 rounded px-1.5 py-0.5">
                          {toolLabel(t)}
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

                  <div className="space-y-2 pt-2">
                    <button
                      onClick={() => handleExportPdf(detail.id, detail.created_at)}
                      disabled={pdfLoading === detail.id}
                      className="w-full text-sm px-4 py-2.5 rounded-lg bg-brand-500 hover:bg-brand-600 text-white font-medium transition-colors flex items-center justify-center gap-2 disabled:opacity-60"
                    >
                      {pdfLoading === detail.id ? '… Genererar rapport' : '↓ Exportera rapport som PDF'}
                    </button>
                    {deleteConfirm === detail.id ? (
                      <div className="flex items-center justify-end gap-2">
                        <span className="text-xs text-slate-500">Bekräfta?</span>
                        <button
                          onClick={() => handleDelete(detail.id)}
                          className="text-xs px-2.5 py-1.5 rounded-lg bg-red-500 text-white hover:bg-red-600"
                        >
                          Ta bort
                        </button>
                        <button
                          onClick={() => setDeleteConfirm(null)}
                          className="text-xs px-2 py-1.5 text-slate-500 hover:text-slate-700"
                        >
                          Avbryt
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setDeleteConfirm(detail.id)}
                        className="w-full text-xs px-3 py-1.5 rounded-lg border border-slate-200 text-slate-400 hover:border-red-300 hover:text-red-500 hover:bg-red-50 transition-colors"
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
      )}
    </div>
  )
}
