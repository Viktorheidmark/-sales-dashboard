import { useState, useRef, useEffect, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import { api } from '../../api/client'
import type { ChatResponse, DateRange, PriorTurnContext, SourceMeta } from '../../api/types'
import { formatDate } from '../../utils/format'
import { MiniAssistantChart } from '../charts/MiniAssistantChart'
import {
  ANALYTICS_DATA_SOURCE,
  formatSourcePeriod,
  isMarketShareResponse,
  resolveResponseDateRange,
  toolLabelSv,
  visibleResponseLimitations,
} from '../../utils/sourcePresentation'

const PROMPT_CARDS = [
  {
    label: 'Produkt i nedgång',
    sub: 'Vilken produkt minskade mest de senaste 30 dagarna?',
    prompt: 'Vilken produkt minskade mest de senaste 30 dagarna?',
  },
  {
    label: 'Försäljningstrend',
    sub: 'Visa försäljningstrend de senaste 90 dagarna',
    prompt: 'Visa försäljningstrend de senaste 90 dagarna',
  },
  {
    label: 'Starkaste region',
    sub: 'Vilken region genererar mest intäkter?',
    prompt: 'Vilken region genererar mest intäkter?',
  },
  {
    label: 'Marknadsandel',
    sub: 'Vad är vår marknadsandel i Mejeri?',
    prompt: 'Vad är vår marknadsandel i Mejeri?',
  },
]

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  statusText?: string
  streamingContent?: string
  response?: ChatResponse
  error?: string
  loading?: boolean
  question?: string
}

interface ChatPanelProps {
  startDate?: string
  endDate?: string
  supplierName?: string
}

const markdownComponents = {
  p: ({ children }: { children?: ReactNode }) => (
    <p className="mb-3 last:mb-0">{children}</p>
  ),
  strong: ({ children }: { children?: ReactNode }) => (
    <strong className="font-semibold text-theme-heading">{children}</strong>
  ),
  ul: ({ children }: { children?: ReactNode }) => (
    <ul className="list-disc pl-5 mt-2 mb-3 space-y-1">{children}</ul>
  ),
  ol: ({ children }: { children?: ReactNode }) => (
    <ol className="list-decimal pl-5 mt-2 mb-3 space-y-1">{children}</ol>
  ),
  li: ({ children }: { children?: ReactNode }) => (
    <li className="text-theme-body">{children}</li>
  ),
}

function buildPriorContext(messages: Message[]): PriorTurnContext | undefined {
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i]
    if (msg.role !== 'assistant' || !msg.response || msg.response.tool_calls.length === 0) {
      continue
    }
    const priorUser = messages.slice(0, i).reverse().find(m => m.role === 'user')
    if (!priorUser) return undefined
    return {
      question: priorUser.content,
      answer: msg.response.answer,
      tool_calls: msg.response.tool_calls,
      sources: msg.response.sources,
    }
  }
  return undefined
}

function SourceSummary({
  sources,
  fallbackDateRange,
}: {
  sources: SourceMeta[]
  fallbackDateRange?: DateRange
}) {
  const dateRange = resolveResponseDateRange(sources, fallbackDateRange)
  const periodLabel = dateRange ? formatSourcePeriod(dateRange) : null

  return (
    <div className="rounded-lg border border-workspace-border/80 bg-workspace-muted/40 px-3 py-2">
      <p className="text-[11px] text-theme-muted leading-snug">
        <span className="font-medium text-theme-body">Datakälla.</span>{' '}
        {periodLabel
          ? `Försäljningsdata ${periodLabel}.`
          : 'Försäljningsdata för vald period.'}
      </p>
    </div>
  )
}

function TechnicalSourceDetails({
  sources,
  fallbackDateRange,
}: {
  sources: SourceMeta[]
  fallbackDateRange?: DateRange
}) {
  return (
    <details className="group/tech">
      <summary className="text-xs text-theme-muted cursor-pointer select-none hover:text-theme-body list-none flex items-center gap-1 w-fit focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50 rounded">
        <span className="transition-transform group-open/tech:rotate-90 text-theme-faint">›</span>
        Visa tekniska detaljer
      </summary>
      <div className="mt-3 pl-3 border-l border-workspace-border/60">
        <p className="text-xs font-medium text-theme-muted mb-3">Analysinformation</p>
        <div className="space-y-4">
          {sources.map((s, i) => {
            const period =
              s.date_range?.start && s.date_range?.end
                ? s.date_range
                : fallbackDateRange

            return (
              <div
                key={i}
                className={`space-y-1.5 text-xs text-theme-muted leading-relaxed ${
                  i > 0 ? 'pt-4 border-t border-workspace-border/50' : ''
                }`}
              >
                <p className="font-medium text-theme-body">{toolLabelSv(s.tool)}</p>
                {s.generated_at && (
                  <p>Data uppdaterad: {formatDate(s.generated_at)}</p>
                )}
                {period?.start && period?.end && (
                  <p>Analysperiod: {formatSourcePeriod(period)}</p>
                )}
                <p>Datakälla: {ANALYTICS_DATA_SOURCE}</p>
              </div>
            )
          })}
        </div>
      </div>
    </details>
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

function LoadingDots() {
  return (
    <span className="flex gap-0.5">
      {[0, 1, 2].map(i => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-theme-faint animate-bounce"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </span>
  )
}

function AssistantBubble({
  msg,
  supplierName,
  fallbackDateRange,
}: {
  msg: Message
  supplierName?: string
  fallbackDateRange?: DateRange
}) {
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

  if (msg.loading && !msg.streamingContent) {
    return (
      <article className="max-w-2xl">
        <div className="flex items-center gap-2.5 text-sm text-theme-muted">
          <LoadingDots />
          <span>{msg.statusText ?? 'Analyserar försäljningsdata…'}</span>
        </div>
      </article>
    )
  }

  if (msg.loading && msg.streamingContent) {
    return (
      <article className="max-w-2xl space-y-1">
        <div className="text-[15px] text-theme-body leading-[1.75]">
          <ReactMarkdown components={markdownComponents}>
            {msg.streamingContent}
          </ReactMarkdown>
          <span className="inline-block w-0.5 h-4 bg-brand-400 animate-pulse align-text-bottom ml-0.5" />
        </div>
      </article>
    )
  }

  if (msg.error) {
    return (
      <article className="max-w-2xl">
        <p className="text-[15px] text-theme-muted leading-relaxed">{msg.error}</p>
      </article>
    )
  }

  const r = msg.response!
  const isGrounded = r.tool_calls.length > 0
  const marketShare = isMarketShareResponse(r)
  const displayLimitations = visibleResponseLimitations(r.limitations, r)

  return (
    <article className="max-w-2xl space-y-5">
      <div className="text-[15px] text-theme-body leading-[1.75]">
        <ReactMarkdown components={markdownComponents}>
          {msg.content}
        </ReactMarkdown>
      </div>

      {r.chart && (
        <div className="pt-1">
          {r.chart.description && (
            <p className="text-xs text-theme-muted mb-2 leading-relaxed">{r.chart.description}</p>
          )}
          <div className="rounded-lg border border-workspace-border bg-workspace-muted/50 px-3 py-2">
            <MiniAssistantChart chart={r.chart} supplierName={supplierName} />
          </div>
          {r.chart.period_note && (
            <p className="mt-1.5 text-[11px] text-theme-muted leading-snug">{r.chart.period_note}</p>
          )}
          {marketShare && (
            <p className="mt-1.5 text-[11px] text-theme-muted leading-snug">
              Konkurrentdata visas endast på aggregerad nivå.
            </p>
          )}
        </div>
      )}

      {displayLimitations.length > 0 && (
        <div className="space-y-1">
          {displayLimitations.map((l, i) => (
            <p key={i} className="text-xs text-amber-600 dark:text-amber-400/90 leading-relaxed">⚠ {l}</p>
          ))}
        </div>
      )}

      {isGrounded && (
        <div className="space-y-3 pt-1">
          <SourceSummary sources={r.sources} fallbackDateRange={fallbackDateRange} />
          <TechnicalSourceDetails sources={r.sources} fallbackDateRange={fallbackDateRange} />
        </div>
      )}

      {isGrounded && (
        <div className="flex items-center gap-3 pt-1">
          <button
            onClick={handleSave}
            disabled={saveState !== 'idle'}
            className={`inline-flex items-center gap-1.5 text-xs transition-colors ${
              saveState === 'saved'
                ? 'text-emerald-400 cursor-default'
                : saveState === 'error'
                ? 'text-red-400 cursor-default'
                : saveState === 'saving'
                ? 'text-theme-muted cursor-wait'
                : 'text-theme-muted hover:text-brand-600 dark:text-brand-400'
            }`}
          >
            <BookmarkIcon filled={saveState === 'saved'} />
            {saveState === 'saved' ? 'Sparad i Insikter' : saveState === 'error' ? 'Misslyckades' : saveState === 'saving' ? 'Sparar…' : 'Spara'}
          </button>
        </div>
      )}
    </article>
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
      const priorContext = buildPriorContext(messages)
      const stream = api.chatStream(
        {
          message: trimmed,
          start_date: startDate,
          end_date: endDate,
          prior_context: priorContext,
        },
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
  const placeholder = supplierName
    ? `Fråga om ${supplierName}s försäljning, produkter eller marknadsandel…`
    : 'Fråga om försäljning, produkter eller marknadsandel…'

  return (
    <div className="flex flex-col flex-1 min-h-0 w-full max-w-3xl mx-auto">
      {/* Conversation workspace */}
      <div className="flex-1 min-h-0 overflow-y-auto scrollbar-thin">
        {isEmpty ? (
          <div className="flex flex-col items-center justify-center min-h-full px-2 py-10 sm:py-16">
            <div className="w-full max-w-xl text-center mb-10">
              <h2 className="text-2xl sm:text-[1.75rem] font-semibold text-theme-heading tracking-tight">
                Vad vill du analysera?
              </h2>
              <p className="mt-3 text-sm text-theme-muted leading-relaxed">
                Fråga om försäljning, produkter, regioner och marknadsandel.
              </p>
            </div>

            <div className="w-full grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {PROMPT_CARDS.map(card => (
                <button
                  key={card.prompt}
                  onClick={() => sendMessage(card.prompt)}
                  disabled={loading}
                  className="text-left px-4 py-3.5 rounded-xl border border-workspace-border bg-workspace-surface hover:border-workspace-border hover:bg-workspace-elevated transition-colors disabled:opacity-40 group focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/40"
                >
                  <p className="text-sm font-medium text-theme-strong group-hover:text-theme-heading">
                    {card.label}
                  </p>
                  <p className="mt-1 text-xs text-theme-muted leading-relaxed">
                    {card.sub}
                  </p>
                </button>
              ))}
            </div>

            {supplierName && (
              <p className="mt-10 text-[11px] text-theme-muted text-center leading-relaxed max-w-sm">
                Analys baserad på syntetisk försäljningsdata för{' '}
                <span className="text-theme-muted">{supplierName}</span>.
                Konkurrentdata visas enbart aggregerat.
              </p>
            )}
          </div>
        ) : (
          <div className="py-6 sm:py-8 space-y-10">
            {messages.map(msg => (
              msg.role === 'user' ? (
                <div key={msg.id} className="flex justify-end">
                  <p className="text-sm font-medium text-theme-strong bg-workspace-elevated border border-workspace-border rounded-xl px-4 py-2.5 max-w-lg leading-snug">
                    {msg.content}
                  </p>
                </div>
              ) : (
                <AssistantBubble
                  key={msg.id}
                  msg={msg}
                  supplierName={supplierName}
                  fallbackDateRange={
                    startDate && endDate ? { start: startDate, end: endDate } : undefined
                  }
                />
              )
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Composer */}
      <div className="shrink-0 pt-4 pb-2">
        <div className="relative rounded-2xl border border-workspace-border bg-workspace-elevated focus-within:border-brand-500/40 focus-within:ring-2 focus-within:ring-brand-500/20 transition-all">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            rows={2}
            disabled={loading}
            className="w-full resize-none rounded-2xl bg-transparent px-5 py-4 pr-14 text-[15px] text-theme-strong placeholder:text-theme-muted focus:outline-none disabled:opacity-50 scrollbar-thin leading-relaxed"
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || loading}
            className="absolute right-3 bottom-3 w-9 h-9 rounded-xl bg-brand-500 hover:bg-brand-600 text-white flex items-center justify-center transition-colors disabled:opacity-35 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
            aria-label="Skicka"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
              <path d="M3.105 2.288a.75.75 0 00-.826.95l1.414 4.926A1.5 1.5 0 005.135 9.25h6.115a.75.75 0 010 1.5H5.135a1.5 1.5 0 00-1.442 1.086l-1.414 4.926a.75.75 0 00.826.95 28.897 28.897 0 0015.293-7.155.75.75 0 000-1.114A28.897 28.897 0 003.105 2.288z" />
            </svg>
          </button>
        </div>
        <p className="text-[11px] text-theme-faint mt-2 text-center">
          Enter för att skicka · Shift+Enter för ny rad
        </p>
      </div>
    </div>
  )
}
