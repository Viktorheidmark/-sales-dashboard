import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { api } from '../../api/client'
import type { ChatResponse, ChartPayload } from '../../api/types'
import { formatDate } from '../../utils/format'

const EXAMPLE_PROMPTS = [
  'Vad är vår totala omsättning de senaste 90 dagarna?',
  'Vilka produkter tappar mest i försäljning?',
  'Hur stor är vår marknadsandel i Kaffe?',
  'Vilka är våra bästsäljande produkter i Stockholm?',
  'Hur ser vår försäljningstrend ut den senaste månaden?',
]

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  response?: ChatResponse
  error?: string
  loading?: boolean
}

interface ChatPanelProps {
  supplierId: string
  startDate?: string
  endDate?: string
  supplierName?: string
}

function MiniChart({ chart }: { chart: ChartPayload }) {
  const COLORS = ['#4169e1', '#a5b4fc', '#c7d2fe', '#e0e7ff']

  if (chart.type === 'line_chart') {
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
  if (chart.type === 'bar_chart') {
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
  if (chart.type === 'pie_chart') {
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
  const label = name.replace('get_', '').replace(/_/g, ' ')
  return (
    <span className="inline-flex items-center gap-1 text-xs bg-brand-50 text-brand-600 border border-brand-100 rounded px-1.5 py-0.5 font-medium">
      <span className="w-1 h-1 rounded-full bg-emerald-400 shrink-0" />
      {label}
    </span>
  )
}

function AssistantBubble({ msg }: { msg: Message }) {
  if (msg.loading) {
    return (
      <div className="flex gap-2 items-start">
        <span className="shrink-0 w-6 h-6 rounded-full bg-brand-500 text-white text-xs flex items-center justify-center font-bold mt-0.5">S</span>
        <div className="bg-white border border-zinc-200 rounded-xl px-4 py-3 text-sm text-zinc-400 flex items-center gap-2">
          <span className="flex gap-0.5">
            {[0, 1, 2].map(i => (
              <span
                key={i}
                className="w-1.5 h-1.5 rounded-full bg-zinc-300 animate-bounce"
                style={{ animationDelay: `${i * 0.15}s` }}
              />
            ))}
          </span>
          Hämtar data via MCP…
        </div>
      </div>
    )
  }

  if (msg.error) {
    return (
      <div className="flex gap-2 items-start">
        <span className="shrink-0 w-6 h-6 rounded-full bg-red-500 text-white text-xs flex items-center justify-center font-bold mt-0.5">!</span>
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
          {msg.error}
        </div>
      </div>
    )
  }

  const r = msg.response!
  return (
    <div className="flex gap-2 items-start">
      <span className="shrink-0 w-6 h-6 rounded-full bg-brand-500 text-white text-xs flex items-center justify-center font-bold mt-0.5">S</span>
      <div className="flex-1 min-w-0 space-y-2">
        <div className="bg-white border border-zinc-200 rounded-xl px-4 py-3">
          <div className="text-sm text-zinc-800 leading-relaxed prose-chat">
            <ReactMarkdown
              components={{
                p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
                strong: ({ children }) => <strong className="font-semibold text-zinc-900">{children}</strong>,
                ul: ({ children }) => <ul className="list-disc list-inside mt-1 mb-1 space-y-0.5">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal list-inside mt-1 mb-1 space-y-0.5">{children}</ol>,
                li: ({ children }) => <li className="text-zinc-800">{children}</li>,
              }}
            >
              {msg.content}
            </ReactMarkdown>
          </div>

          {/* Optional chart */}
          {r.chart && (
            <div className="mt-3 pt-3 border-t border-zinc-100">
              <p className="text-xs font-medium text-zinc-500 mb-2">{r.chart.title}</p>
              <MiniChart chart={r.chart} />
            </div>
          )}

          {/* Limitations */}
          {r.limitations.length > 0 && (
            <div className="mt-3 pt-2 border-t border-amber-100">
              {r.limitations.map((l, i) => (
                <p key={i} className="text-xs text-amber-600">⚠ {l}</p>
              ))}
            </div>
          )}
        </div>

        {/* Tool + source indicators */}
        {r.tool_calls.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 px-1">
            <span className="text-xs text-zinc-400">via</span>
            {r.tool_calls.map(t => <ToolBadge key={t} name={t} />)}
            {r.sources[0]?.generated_at && (
              <span className="text-xs text-zinc-400 ml-auto">
                {formatDate(r.sources[0].generated_at)}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export function ChatPanel({ supplierId, startDate, endDate, supplierName }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || loading) return

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: trimmed,
    }
    const loadingMsg: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      loading: true,
    }

    setMessages(prev => [...prev, userMsg, loadingMsg])
    setInput('')
    setLoading(true)

    try {
      const response = await api.chat({
        message: trimmed,
        supplier_id: supplierId,
        start_date: startDate,
        end_date: endDate,
      })

      setMessages(prev => prev.map(m =>
        m.id === loadingMsg.id
          ? { ...m, loading: false, content: response.answer, response }
          : m
      ))
    } catch (err) {
      const errorText = err instanceof Error ? err.message : 'Något gick fel. Försök igen.'
      setMessages(prev => prev.map(m =>
        m.id === loadingMsg.id
          ? { ...m, loading: false, content: '', error: errorText }
          : m
      ))
    } finally {
      setLoading(false)
      inputRef.current?.focus()
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
    <div className="bg-white rounded-xl border border-zinc-200 shadow-sm flex flex-col" style={{ minHeight: 480 }}>
      {/* Header */}
      <div className="px-6 pt-5 pb-3 border-b border-zinc-100 shrink-0">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400" />
          <h2 className="text-sm font-semibold text-zinc-700">Analytics Copilot</h2>
          <span className="ml-auto text-xs text-zinc-400">Grounded via MCP · svarar på svenska</span>
        </div>
        {supplierName && (
          <p className="text-xs text-zinc-400 mt-0.5">
            Kontext: <span className="text-zinc-600 font-medium">{supplierName}</span>
          </p>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4 scrollbar-thin">
        {isEmpty ? (
          <div className="flex flex-col items-center justify-center h-full gap-4 py-8">
            <p className="text-sm text-zinc-400 text-center">
              Ställ en fråga om er försäljningsdata.<br />
              Alla svar baseras på verklig analytikdata.
            </p>
            <div className="flex flex-col gap-2 w-full max-w-sm">
              {EXAMPLE_PROMPTS.map(p => (
                <button
                  key={p}
                  onClick={() => sendMessage(p)}
                  className="text-left text-xs px-3 py-2 rounded-lg border border-zinc-200 text-zinc-600 hover:border-brand-300 hover:text-brand-700 hover:bg-brand-50 transition-colors"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map(msg => (
            msg.role === 'user' ? (
              <div key={msg.id} className="flex justify-end">
                <div className="bg-brand-500 text-white rounded-xl px-4 py-2.5 text-sm max-w-xs">
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
      <div className="px-4 pb-4 pt-2 border-t border-zinc-100 shrink-0">
        <div className="flex gap-2 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Skriv en fråga… (Enter för att skicka)"
            rows={2}
            disabled={loading}
            className="flex-1 resize-none rounded-lg border border-zinc-200 px-3 py-2 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-brand-400 focus:border-transparent disabled:opacity-50 scrollbar-thin"
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
        <p className="text-xs text-zinc-400 mt-1.5 px-1">
          Svar genereras enbart från MCP-analytikverktyg · Ingen fri SQL-åtkomst
        </p>
      </div>
    </div>
  )
}
