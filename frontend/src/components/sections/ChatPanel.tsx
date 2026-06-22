import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { api } from '../../api/client'
import type { ChatResponse, ChartPayload, SourceMeta } from '../../api/types'
import { formatDate } from '../../utils/format'

const PROMPT_CARDS = [
  {
    label: 'Produkt i nedgång',
    sub: 'Vilken produkt minskade mest de senaste 30 dagarna?',
    prompt: 'Vilken produkt minskade mest de senaste 30 dagarna?',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
        <polyline points="3 7 9 13 13 9 21 17" />
        <polyline points="15 17 21 17 21 11" />
      </svg>
    ),
  },
  {
    label: 'Försäljningstrend',
    sub: 'Visa försäljningstrend de senaste 90 dagarna',
    prompt: 'Visa försäljningstrend de senaste 90 dagarna',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
        <polyline points="3 17 9 11 13 15 21 7" />
        <polyline points="15 7 21 7 21 13" />
      </svg>
    ),
  },
  {
    label: 'Starkaste region',
    sub: 'Vilken region genererar mest intäkter?',
    prompt: 'Vilken region genererar mest intäkter?',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
        <circle cx="12" cy="10" r="3" />
        <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" />
      </svg>
    ),
  },
  {
    label: 'Marknadsandel',
    sub: 'Vad är vår marknadsandel i Mejeri?',
    prompt: 'Vad är vår marknadsandel i Mejeri?',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
        <path d="M12 2v10l6.9 6.9" />
        <circle cx="12" cy="12" r="10" />
      </svg>
    ),
  },
]

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  // Streaming-specific fields — only set on assistant messages during/after stream
  statusText?: string        // current progress label (shown before first delta)
  streamingContent?: string  // accumulated delta text (shown during streaming)
  response?: ChatResponse    // set from `complete` event
  error?: string
  loading?: boolean
  question?: string
}

interface ChatPanelProps {
  startDate?: string
  endDate?: string
  supplierName?: string
}

function MiniChart({ chart }: { chart: ChartPayload }) {
  const COLORS = ['#4169e1', '#a5b4fc', '#c7d2fe', '#e0e7ff']
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

function ToolBadge({ name }: { name: string }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs bg-zinc-100 text-zinc-500 rounded px-1.5 py-0.5">
      {name.replace('get_', '').replace(/_/g, ' ')}
    </span>
  )
}

type SaveState = 'idle' | 'saving' | 'saved' | 'error'

function BookmarkIcon({ filled }: { filled?: boolean }) {
  return (
    <svg className="w-3.5 h-3.5" fill={filled ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 3h14a1 1 0 011 1v17l-7-4-7 4V4a1 1 0 011-1z" />
    </svg>
  )
}

function AssistantBubble({ msg }: { msg: Message }) {
  const [saveState, setSaveState] = useState<SaveState>('idle')

  const handleSave = async () => {
    if (!msg.question || !msg.response || saveState !== 'idle') return
    const r = msg.response
    if (r.tool_calls.length === 0) return
    setSaveState('saving')
    try {
      await api.saveInsight({
        question: msg.question,
        answer: r.answer,
        chart: r.chart ?? undefined,
        tool_calls: r.tool_calls,
        sources: r.sources as unknown as SourceMeta[],
        limitations: r.limitations,
      })
      setSaveState('saved')
    } catch {
      setSaveState('error')
    }
  }

  // ── Loading: show status text + bouncing dots (before any delta arrives) ──
  if (msg.loading && !msg.streamingContent) {
    return (
      <div className="flex gap-3 items-start">
        <span className="shrink-0 w-7 h-7 rounded-full bg-brand-500 text-white text-xs flex items-center justify-center font-bold mt-0.5">S</span>
        <div className="bg-white border border-zinc-200 rounded-xl px-4 py-3 space-y-1.5">
          <div className="flex items-center gap-2 text-sm text-zinc-500">
            <span className="flex gap-0.5">
              {[0, 1, 2].map(i => (
                <span
                  key={i}
                  className="w-1.5 h-1.5 rounded-full bg-zinc-300 animate-bounce"
                  style={{ animationDelay: `${i * 0.15}s` }}
                />
              ))}
            </span>
            {msg.statusText ?? 'Analyserar försäljningsdata…'}
          </div>
          {msg.statusText === 'Hämtar relevanta analysdata…' && (
            <p className="text-xs text-zinc-400">Hämtar relevanta signaler från analyslagret</p>
          )}
        </div>
      </div>
    )
  }

  // ── Streaming: show partial answer as it arrives ──
  if (msg.loading && msg.streamingContent) {
    return (
      <div className="flex gap-3 items-start">
        <span className="shrink-0 w-7 h-7 rounded-full bg-brand-500 text-white text-xs flex items-center justify-center font-bold mt-0.5">S</span>
        <div className="bg-white border border-zinc-200 rounded-xl px-4 py-3">
          <div className="flex items-center gap-1.5 pb-2 border-b border-zinc-100 mb-2">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0 animate-pulse" />
            <span className="text-xs text-zinc-500">Svar grundat i analyserad demodata</span>
          </div>
          <div className="text-sm text-zinc-800 leading-relaxed">
            <ReactMarkdown
              components={{
                p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
                strong: ({ children }) => <strong className="font-semibold text-zinc-900">{children}</strong>,
                ul: ({ children }) => <ul className="list-disc list-inside mt-1 mb-1 space-y-0.5">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal list-inside mt-1 mb-1 space-y-0.5">{children}</ol>,
                li: ({ children }) => <li className="text-zinc-700">{children}</li>,
              }}
            >
              {msg.streamingContent}
            </ReactMarkdown>
            <span className="inline-block w-0.5 h-4 bg-brand-400 animate-pulse align-text-bottom ml-0.5" />
          </div>
        </div>
      </div>
    )
  }

  // ── Error state ──
  if (msg.error) {
    return (
      <div className="flex gap-3 items-start">
        <span className="shrink-0 w-7 h-7 rounded-full bg-zinc-300 text-zinc-600 text-xs flex items-center justify-center font-bold mt-0.5">!</span>
        <div className="bg-zinc-50 border border-zinc-200 rounded-xl px-4 py-3 text-sm text-zinc-600">
          {msg.error}
        </div>
      </div>
    )
  }

  // ── Complete response ──
  const r = msg.response!
  const isGrounded = r.tool_calls.length > 0

  return (
    <div className="flex gap-3 items-start">
      <span className="shrink-0 w-7 h-7 rounded-full bg-brand-500 text-white text-xs flex items-center justify-center font-bold mt-0.5">S</span>
      <div className="flex-1 min-w-0 space-y-2">
        <div className="bg-white border border-zinc-200 rounded-xl px-4 py-3 space-y-3">
          {isGrounded && (
            <div className="flex items-center gap-1.5 pb-2 border-b border-zinc-100">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />
              <span className="text-xs text-zinc-500">Svar grundat i analyserad demodata</span>
            </div>
          )}
          <div className="text-sm text-zinc-800 leading-relaxed">
            <ReactMarkdown
              components={{
                p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
                strong: ({ children }) => <strong className="font-semibold text-zinc-900">{children}</strong>,
                ul: ({ children }) => <ul className="list-disc list-inside mt-1 mb-1 space-y-0.5">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal list-inside mt-1 mb-1 space-y-0.5">{children}</ol>,
                li: ({ children }) => <li className="text-zinc-700">{children}</li>,
              }}
            >
              {msg.content}
            </ReactMarkdown>
          </div>
          {r.chart && (
            <div className="mt-1 pt-3 border-t border-zinc-100">
              <p className="text-xs font-semibold text-zinc-700 mb-0.5">{r.chart.title}</p>
              {r.chart.description && (
                <p className="text-xs text-zinc-400 mb-2">{r.chart.description}</p>
              )}
              <MiniChart chart={r.chart} />
              <p className="text-xs text-zinc-400 mt-1">
                via {r.chart.source_tool} · {r.chart.generated_from_row_count} rader
              </p>
            </div>
          )}
          {r.limitations.length > 0 && (
            <div className="pt-2 border-t border-zinc-100 space-y-0.5">
              {r.limitations.map((l, i) => (
                <p key={i} className="text-xs text-amber-600">⚠ {l}</p>
              ))}
            </div>
          )}

          {isGrounded && (
            <details className="pt-2 border-t border-zinc-100 group/sources">
              <summary className="text-xs font-medium text-zinc-500 cursor-pointer select-none hover:text-zinc-700 list-none flex items-center gap-1">
                <span className="transition-transform group-open/sources:rotate-90">›</span>
                Källor och metodik
              </summary>
              <div className="mt-2 space-y-2">
                <div className="flex flex-wrap items-center gap-1.5">
                  {r.tool_calls.map(t => <ToolBadge key={t} name={t} />)}
                </div>
                {r.sources.map((s, i) => (
                  <div key={i} className="text-xs text-zinc-500 bg-zinc-50 rounded-lg px-3 py-2 space-y-0.5">
                    <p>
                      <span className="font-medium text-zinc-600">{s.tool}</span>
                      {s.source && <span className="text-zinc-400"> · {s.source}</span>}
                    </p>
                    {s.generated_at && (
                      <p className="text-zinc-400">Beräknad: {formatDate(s.generated_at)}</p>
                    )}
                    {s.row_count !== undefined && (
                      <p className="text-zinc-400">{s.row_count} rader</p>
                    )}
                    {s.date_range && (
                      <p className="text-zinc-400">Period: {s.date_range.start} → {s.date_range.end}</p>
                    )}
                    {s.limitations?.map((l, j) => (
                      <p key={j} className="text-amber-600">⚠ {l}</p>
                    ))}
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>

        {isGrounded && (
          <div className="flex flex-wrap items-center gap-1.5 px-1">
            {r.sources[0]?.generated_at && (
              <span className="text-xs text-zinc-400">{formatDate(r.sources[0].generated_at)}</span>
            )}
            <button
              onClick={handleSave}
              disabled={saveState !== 'idle'}
              className={`ml-auto inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-lg border transition-colors ${
                saveState === 'saved'
                  ? 'border-emerald-200 text-emerald-600 bg-emerald-50 cursor-default'
                  : saveState === 'error'
                  ? 'border-red-200 text-red-500 bg-red-50 cursor-default'
                  : saveState === 'saving'
                  ? 'border-zinc-200 text-zinc-400 cursor-wait'
                  : 'border-zinc-200 text-zinc-500 hover:border-brand-300 hover:text-brand-600 hover:bg-brand-50'
              }`}
            >
              <BookmarkIcon filled={saveState === 'saved'} />
              {saveState === 'saved' ? 'Sparad i Insikter' : saveState === 'error' ? 'Misslyckades' : saveState === 'saving' ? '…' : 'Spara'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export function ChatPanel({ startDate, endDate, supplierName }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      abortRef.current?.abort()
    }
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || loading) return

    // Abort any in-flight stream
    abortRef.current?.abort()
    const abort = new AbortController()
    abortRef.current = abort

    const userMsg: Message = { id: crypto.randomUUID(), role: 'user', content: trimmed }
    const assistantId = crypto.randomUUID()
    const loadingMsg: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      loading: true,
      statusText: 'Analyserar försäljningsdata…',
      question: trimmed,
    }

    setMessages(prev => [...prev, userMsg, loadingMsg])
    setInput('')
    setLoading(true)

    const update = (patch: Partial<Message>) => {
      if (!mountedRef.current) return
      setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, ...patch } : m))
    }

    try {
      const stream = api.chatStream(
        { message: trimmed, start_date: startDate, end_date: endDate },
        abort.signal,
      )

      for await (const event of stream) {
        if (!mountedRef.current || abort.signal.aborted) break

        if (event.type === 'status') {
          update({ statusText: event.text })
        } else if (event.type === 'delta') {
          setMessages(prev => prev.map(m =>
            m.id === assistantId
              ? { ...m, streamingContent: (m.streamingContent ?? '') + event.text }
              : m
          ))
        } else if (event.type === 'complete') {
          const response: ChatResponse = {
            answer: event.answer,
            tool_calls: event.tool_calls,
            sources: event.sources,
            chart: event.chart,
            limitations: event.limitations,
            supplier_id: event.supplier_id,
            generated_at: event.generated_at,
          }
          update({
            loading: false,
            content: event.answer,
            streamingContent: undefined,
            statusText: undefined,
            response,
          })
        } else if (event.type === 'error') {
          update({
            loading: false,
            streamingContent: undefined,
            statusText: undefined,
            error: event.message,
          })
        }
      }
    } catch (err) {
      if (!mountedRef.current) return
      if (err instanceof Error && err.name === 'AbortError') return
      update({
        loading: false,
        streamingContent: undefined,
        statusText: undefined,
        error: 'Anslutningen avbröts. Försök igen.',
      })
    } finally {
      if (mountedRef.current) {
        setLoading(false)
        inputRef.current?.focus()
      }
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  const isEmpty = messages.length === 0

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-sm flex flex-col" style={{ minHeight: 620 }}>
      {/* Status bar */}
      <div className="px-6 py-3 border-b border-slate-100 shrink-0 flex items-center justify-between gap-4">
        <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />
          Svar grundat i analyserad demodata
        </span>
        {supplierName && (
          <span className="text-xs text-slate-400">Analys för <span className="text-slate-500">{supplierName}</span></span>
        )}
      </div>

      {/* Messages / Empty state */}
      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4 scrollbar-thin">
        {isEmpty ? (
          <div className="space-y-4">
            <div>
              <p className="text-sm font-semibold text-zinc-800">Vad vill du förstå bättre?</p>
              <p className="text-xs text-zinc-400 mt-0.5">Välj ett område nedan eller skriv en egen fråga.</p>
              <p className="text-xs text-zinc-400 mt-2">Trender · Produkter · Regioner · Marknadsandel</p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {PROMPT_CARDS.map(card => (
                <button
                  key={card.prompt}
                  onClick={() => sendMessage(card.prompt)}
                  disabled={loading}
                  className="text-left p-4 rounded-xl border border-slate-100 hover:border-brand-300 hover:bg-brand-50 bg-slate-50 transition-colors disabled:opacity-40 group"
                >
                  <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest mb-1.5 group-hover:text-brand-500 transition-colors">{card.label}</p>
                  <p className="text-sm font-medium text-slate-800 leading-snug group-hover:text-brand-700 transition-colors">{card.sub}</p>
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map(msg => (
            msg.role === 'user' ? (
              <div key={msg.id} className="flex justify-end">
                <div className="bg-brand-500 text-white rounded-xl px-4 py-2.5 text-sm max-w-xs leading-relaxed">
                  {msg.content}
                </div>
              </div>
            ) : (
              <AssistantBubble key={msg.id} msg={msg} />
            )
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-4 pb-4 pt-3 border-t border-zinc-100 shrink-0">
        <div className="flex gap-2 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Fråga om försäljning, produkter eller marknadsandel…"
            rows={2}
            disabled={loading}
            className="flex-1 resize-none rounded-lg border border-zinc-300 px-3 py-2 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent disabled:opacity-50 scrollbar-thin"
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || loading}
            className="shrink-0 w-9 h-9 rounded-lg bg-brand-500 hover:bg-brand-600 text-white flex items-center justify-center transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            aria-label="Skicka"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
              <path d="M3.105 2.288a.75.75 0 00-.826.95l1.414 4.926A1.5 1.5 0 005.135 9.25h6.115a.75.75 0 010 1.5H5.135a1.5 1.5 0 00-1.442 1.086l-1.414 4.926a.75.75 0 00.826.95 28.897 28.897 0 0015.293-7.155.75.75 0 000-1.114A28.897 28.897 0 003.105 2.288z" />
            </svg>
          </button>
        </div>
        <p className="text-xs text-zinc-400 mt-1.5 px-0.5">
          Enter för att skicka · Svar grundas i MCP-analytikverktyg
        </p>
      </div>
    </div>
  )
}
