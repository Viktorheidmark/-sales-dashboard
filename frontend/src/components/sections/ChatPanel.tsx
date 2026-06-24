import { useState, useRef, useEffect, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import { api } from '../../api/client'
import type { ChatResponse, DateRange, InsightSummary, PriorTurnContext, SourceMeta } from '../../api/types'
import { formatDate } from '../../utils/format'
import { MiniAssistantChart } from '../charts/MiniAssistantChart'
import { DeepDivePanel } from '../charts/DeepDivePanel'
import {
  formatSourcePeriod,
  isMarketShareResponse,
  resolveResponseDateRange,
  visibleResponseLimitations,
} from '../../utils/sourcePresentation'


const LOADING_STATUSES = [
  'Analyserar försäljningsdata…',
  'Hämtar relevanta jämförelser…',
  'Förbereder analys…',
] as const

function loadingStatusFor(message: string): string {
  const idx = message.trim().length % LOADING_STATUSES.length
  return LOADING_STATUSES[idx]
}

function userFacingError(_raw?: string): string {
  return 'Analysen kunde inte slutföras. Försök igen.'
}

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
  initialPrompt?: string
}

// ---------------------------------------------------------------------------
// Markdown components (unchanged)
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Helpers (unchanged)
// ---------------------------------------------------------------------------

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
      has_chart: msg.response.chart != null,
      analysis_context: msg.response.analysis_context ?? undefined,
    }
  }
  return undefined
}

// ---------------------------------------------------------------------------
// SourceSummary (unchanged)
// ---------------------------------------------------------------------------

function SourceSummary({
  sources,
  fallbackDateRange,
}: {
  sources: SourceMeta[]
  fallbackDateRange?: DateRange
}) {
  const dateRange = resolveResponseDateRange(sources, fallbackDateRange)
  if (!dateRange) return null
  const periodLabel = formatSourcePeriod(dateRange)

  return (
    <p className="text-[10px] text-theme-faint leading-snug">
      Data: Försäljningsdata · {periodLabel}
    </p>
  )
}

// ---------------------------------------------------------------------------
// TechnicalSourceDetails (unchanged)
// ---------------------------------------------------------------------------

function TechnicalSourceDetails({
  sources,
  fallbackDateRange,
}: {
  sources: SourceMeta[]
  fallbackDateRange?: DateRange
}) {
  if (sources.length === 0) return null

  return (
    <details className="group/tech mt-1">
      <summary className="text-[10px] text-theme-faint cursor-pointer select-none hover:text-theme-muted list-none flex items-center gap-1 w-fit focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50 rounded">
        <span className="transition-transform group-open/tech:rotate-90 text-theme-faint">›</span>
        Visa tekniska detaljer
      </summary>
      <div className="mt-2 pl-2 border-l border-workspace-border/40">
        <div className="space-y-3">
          {sources.map((s, i) => {
            const period =
              s.date_range?.start && s.date_range?.end
                ? s.date_range
                : fallbackDateRange

            return (
              <div
                key={i}
                className={`space-y-1 text-[10px] text-theme-faint leading-relaxed ${
                  i > 0 ? 'pt-3 border-t border-workspace-border/40' : ''
                }`}
              >
                {s.generated_at && (
                  <p>Uppdaterad: {formatDate(s.generated_at)}</p>
                )}
                {period?.start && period?.end && (
                  <p>Period: {formatSourcePeriod(period)}</p>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </details>
  )
}

// ---------------------------------------------------------------------------
// Small utilities (unchanged)
// ---------------------------------------------------------------------------

type SaveState = 'idle' | 'saving' | 'saved' | 'error'

function BookmarkIcon({ filled }: { filled?: boolean }) {
  return (
    <svg className="w-3.5 h-3.5" fill={filled ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 3h14a1 1 0 011 1v17l-7-4-7 4V4a1 1 0 011-1z" />
    </svg>
  )
}

function SendButton({ onClick, disabled, loading }: { onClick: () => void; disabled: boolean; loading: boolean }) {
  const [hovered, setHovered] = useState(false)
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-busy={loading}
      aria-label="Skicka"
      onMouseEnter={() => !disabled && setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        position: 'absolute',
        right: 10,
        top: '50%',
        transform: hovered && !disabled ? 'translateY(-50%) scale(1.05)' : 'translateY(-50%)',
        width: 40,
        height: 40,
        borderRadius: '50%',
        background: disabled ? 'var(--text-muted)' : 'var(--accent)',
        color: 'white',
        border: 'none',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.3 : 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        transition: 'transform 0.15s, opacity 0.15s, background 0.15s',
        flexShrink: 0,
      }}
      className="focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
    >
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" style={{ width: 15, height: 15 }}>
        <path d="M3.105 2.288a.75.75 0 00-.826.95l1.414 4.926A1.5 1.5 0 005.135 9.25h6.115a.75.75 0 010 1.5H5.135a1.5 1.5 0 00-1.442 1.086l-1.414 4.926a.75.75 0 00.826.95 28.897 28.897 0 0015.293-7.155.75.75 0 000-1.114A28.897 28.897 0 003.105 2.288z" />
      </svg>
    </button>
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

// ---------------------------------------------------------------------------
// ChartBlock (unchanged)
// ---------------------------------------------------------------------------

function ChartBlock({
  chart,
  supplierName,
}: {
  chart: NonNullable<ChatResponse['chart']>
  supplierName?: string
}) {
  const selfContained = chart.chart_type === 'insight_card' || chart.chart_type === 'empty_state'
  const isSecondary = chart.chart_role === 'secondary' || chart.compact
  if (selfContained) {
    return <MiniAssistantChart chart={chart} supplierName={supplierName} />
  }
  return (
    <div className={`assistant-chart-card ${isSecondary ? 'assistant-chart-card-secondary' : ''}`}>
      {chart.title && (
        <h3 className={`font-semibold text-theme-heading leading-snug ${isSecondary ? 'text-xs' : 'text-sm'}`}>
          {chart.title}
        </h3>
      )}
      {chart.description && (
        <p className={`text-theme-muted mt-0.5 mb-3 leading-relaxed ${isSecondary ? 'text-[11px]' : 'text-xs'}`}>
          {chart.description}
        </p>
      )}
      <MiniAssistantChart chart={chart} supplierName={supplierName} compact={isSecondary} />
      {chart.stability_note && (
        <p className="mt-2 text-[11px] text-theme-muted leading-snug italic">{chart.stability_note}</p>
      )}
      {chart.period_note && (
        <p className="mt-2 text-[11px] text-theme-muted leading-snug">{chart.period_note}</p>
      )}
    </div>
  )
}

function UnsupportedAnswerCard({ content }: { content: string }) {
  return (
    <div className="assistant-support-card flex items-start gap-3">
      <span className="shrink-0 w-8 h-8 rounded-lg bg-workspace-muted border border-workspace-border/60 flex items-center justify-center text-theme-muted" aria-hidden>
        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
        </svg>
      </span>
      <p className="min-w-0 text-sm text-theme-body leading-relaxed">{content}</p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// AssistantBubble — styled with new message card design
// ---------------------------------------------------------------------------

function AssistantBubble({
  msg,
  supplierName,
  fallbackDateRange,
  onSendMessage,
}: {
  msg: Message
  supplierName?: string
  fallbackDateRange?: DateRange
  onSendMessage: (text: string) => void
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
      <article
        className="self-start w-full py-2"
        style={{ animation: 'chatMsgIn 0.25s ease-out both' }}
      >
        <div className="flex items-center gap-2.5 text-sm text-theme-muted">
          <LoadingDots />
          <span>{msg.statusText ?? 'Analyserar försäljningsdata…'}</span>
        </div>
      </article>
    )
  }

  if (msg.loading && msg.streamingContent) {
    return (
      <article
        className="self-start w-full py-1"
        style={{ animation: 'chatMsgIn 0.25s ease-out both' }}
      >
        <div style={{ fontSize: 15, color: 'var(--text-primary)', lineHeight: 1.6 }} className="min-h-[4.5rem]">
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
      <article
        className="self-start w-full py-1 space-y-3"
        style={{ animation: 'chatMsgIn 0.25s ease-out both' }}
      >
        <p className="text-sm text-theme-body leading-relaxed">{msg.error}</p>
        {msg.question && (
          <button
            type="button"
            onClick={() => onSendMessage(msg.question!)}
            className="text-xs px-2.5 py-1 rounded-full border border-workspace-border bg-workspace-surface text-theme-body hover:border-brand-400/60 hover:text-brand-600 dark:hover:text-brand-400 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50"
          >
            Försök igen
          </button>
        )}
      </article>
    )
  }

  const r = msg.response!
  const isGrounded = r.tool_calls.length > 0
  const displayLimitations = visibleResponseLimitations(r.limitations, r)
  const sourcePeriod = resolveResponseDateRange(r.sources, fallbackDateRange)
  const showSourceFooter = isGrounded && (sourcePeriod != null || r.sources.length > 0)

  return (
    <article
      className="self-start w-full space-y-3"
      style={{ padding: '4px 0', maxWidth: '80%', animation: 'chatMsgIn 0.3s ease-out both' }}
    >
      {!isGrounded ? (
        <UnsupportedAnswerCard content={msg.content} />
      ) : (
        <div style={{ fontSize: 15, color: 'var(--text-primary)', lineHeight: 1.6 }}>
          <ReactMarkdown components={markdownComponents}>
            {msg.content}
          </ReactMarkdown>
        </div>
      )}

      {isGrounded && !r.chart && r.tool_calls.includes('get_sales_over_time') && !r.deep_dive && (
        <div className="flex items-center gap-4 pt-1">
          <button
            onClick={() => onSendMessage('Visa diagram')}
            className="text-xs text-brand-500 hover:text-brand-600 dark:text-brand-400 dark:hover:text-brand-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50 rounded"
          >
            Visa diagram →
          </button>
          <button
            onClick={() => onSendMessage('Visa trenden')}
            className="text-xs text-theme-muted hover:text-theme-body focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50 rounded"
          >
            Visa trend →
          </button>
        </div>
      )}

      {r.chart && (
        <div className="pt-1">
          <ChartBlock chart={r.chart} supplierName={supplierName} />
          {isMarketShareResponse(r) && (
            <p className="mt-1.5 text-[11px] text-theme-muted leading-snug">
              Konkurrentdata visas endast på aggregerad nivå.
            </p>
          )}
        </div>
      )}

      {(r.charts ?? []).map((extraChart, i) => (
        <div key={`chart-${i}`} className="pt-1">
          <ChartBlock chart={extraChart} supplierName={supplierName} />
        </div>
      ))}

      {r.deep_dive && (
        <div className="pt-1">
          <DeepDivePanel deepDive={r.deep_dive} />
        </div>
      )}

      {isGrounded && (
        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saveState !== 'idle'}
            className={`inline-flex items-center gap-1.5 text-xs transition-colors ${
              saveState === 'saved'
                ? 'text-emerald-600 dark:text-emerald-400 cursor-default'
                : saveState === 'error'
                ? 'text-red-500 dark:text-red-400 cursor-default'
                : saveState === 'saving'
                ? 'text-theme-muted cursor-wait'
                : 'text-theme-muted hover:text-brand-600 dark:hover:text-brand-400'
            }`}
          >
            <BookmarkIcon filled={saveState === 'saved'} />
            {saveState === 'saved'
              ? 'Insikten har sparats'
              : saveState === 'error'
              ? 'Kunde inte spara'
              : saveState === 'saving'
              ? 'Sparar…'
              : 'Spara insikt'}
          </button>
        </div>
      )}

      {displayLimitations.length > 0 && (
        <div className="space-y-1">
          {displayLimitations.map((l, i) => (
            <p key={i} className="text-xs text-amber-600 dark:text-amber-400/90 leading-relaxed">⚠ {l}</p>
          ))}
        </div>
      )}

      {showSourceFooter && (
        <div className="space-y-1 pt-2 border-t border-workspace-border/30">
          <SourceSummary sources={r.sources} fallbackDateRange={fallbackDateRange} />
          <TechnicalSourceDetails sources={r.sources} fallbackDateRange={fallbackDateRange} />
        </div>
      )}
    </article>
  )
}

// ---------------------------------------------------------------------------
// InsightChip — single chip with hover via inline state
// ---------------------------------------------------------------------------

function InsightChip({ insight, onSendMessage }: { insight: InsightSummary; onSendMessage: (t: string) => void }) {
  const [hovered, setHovered] = useState(false)
  return (
    <button
      key={insight.id}
      onClick={() => onSendMessage(insight.question)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '6px 14px',
        borderRadius: 20,
        background: 'var(--bg-card)',
        border: `1px solid ${hovered ? 'var(--accent)' : 'var(--border-subtle)'}`,
        fontSize: 12,
        color: hovered ? 'var(--accent)' : 'var(--text-secondary)',
        cursor: 'pointer',
        maxWidth: 200,
        overflow: 'hidden',
        whiteSpace: 'nowrap',
        textOverflow: 'ellipsis',
        transition: 'border-color 0.15s, color 0.15s',
      }}
      className="focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50"
    >
      <svg style={{ width: 12, height: 12, opacity: 0.5, flexShrink: 0 }} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {insight.question.length > 40 ? insight.question.slice(0, 40) + '…' : insight.question}
      </span>
    </button>
  )
}

// ---------------------------------------------------------------------------
// RecentInsightsRow — shows up to 3 recent saved insights as chips
// ---------------------------------------------------------------------------

function RecentInsightsRow({ onSendMessage }: { onSendMessage: (text: string) => void }) {
  const [insights, setInsights] = useState<InsightSummary[]>([])

  useEffect(() => {
    api.listInsights(3).then(setInsights).catch(() => {})
  }, [])

  if (insights.length === 0) return null

  return (
    <div style={{ animation: 'fadeInUp 0.4s ease-out 0.15s both', textAlign: 'center' }}>
      <p style={{
        fontSize: 11,
        fontWeight: 500,
        letterSpacing: '0.05em',
        color: 'var(--text-muted)',
        textTransform: 'uppercase',
        marginBottom: 8,
      }}>
        Senaste analyser
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
        {insights.map(insight => (
          <InsightChip key={insight.id} insight={insight} onSendMessage={onSendMessage} />
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ChatInputBar — shared pill input used in both empty and active states
// ---------------------------------------------------------------------------

function ChatInputBar({
  inputRef,
  value,
  onChange,
  onKeyDown,
  placeholder,
  disabled,
  onSend,
}: {
  inputRef: React.RefObject<HTMLTextAreaElement>
  value: string
  onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void
  placeholder: string
  disabled: boolean
  onSend: () => void
}) {
  return (
    <div
      className="relative flex items-center transition-all"
      style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        borderRadius: 28,
      }}
      onFocusCapture={e => {
        const el = e.currentTarget
        el.style.borderColor = 'var(--accent)'
        el.style.boxShadow = 'var(--shadow-focus)'
      }}
      onBlurCapture={e => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) {
          const el = e.currentTarget
          el.style.borderColor = 'var(--border-color)'
          el.style.boxShadow = ''
        }
      }}
    >
      <textarea
        ref={inputRef}
        value={value}
        onChange={onChange}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        rows={1}
        disabled={disabled}
        className="flex-1 resize-none bg-transparent text-theme-strong placeholder:text-theme-muted focus:outline-none disabled:opacity-50 scrollbar-thin"
        style={{
          fontSize: 16,
          color: 'var(--text-primary)',
          borderRadius: 28,
          minHeight: 56,
          padding: '16px 56px 16px 24px',
          lineHeight: 1.5,
        }}
      />
      <SendButton onClick={onSend} disabled={!value.trim() || disabled} loading={disabled} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main ChatPanel
// ---------------------------------------------------------------------------

export function ChatPanel({ startDate, endDate, supplierName, initialPrompt }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState(initialPrompt ?? '')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const mountedRef = useRef(true)
  const chatSessionRef = useRef(0)

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
      statusText: loadingStatusFor(trimmed),
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
      const sessionAtSend = chatSessionRef.current
      const priorContext = messages.length > 0 ? buildPriorContext(messages) : undefined
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
        if (!mountedRef.current || abort.signal.aborted || chatSessionRef.current !== sessionAtSend) break

        if (event.type === 'status') {
          update({ statusText: event.text || loadingStatusFor(trimmed) })
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
            charts: event.charts,
            deep_dive: event.deep_dive,
            follow_up_actions: event.follow_up_actions,
            analysis_context: event.analysis_context,
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
            error: userFacingError(event.message),
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
        error: userFacingError(),
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

  const resetChat = () => {
    abortRef.current?.abort()
    abortRef.current = null
    chatSessionRef.current += 1
    setMessages([])
    setInput('')
    setLoading(false)
    inputRef.current?.focus()
  }

  const isEmpty = messages.length === 0
  const placeholder = 'Vad kan jag hjälpa dig med?'

  const inputBar = (
    <ChatInputBar
      inputRef={inputRef}
      value={input}
      onChange={e => setInput(e.target.value)}
      onKeyDown={handleKeyDown}
      placeholder={placeholder}
      disabled={loading}
      onSend={() => sendMessage(input)}
    />
  )

  return (
    <>
      <style>{`
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(10px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes chatMsgIn {
          from { opacity: 0; transform: translateY(8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      <div
        className="flex flex-col flex-1 min-h-0 w-full"
        style={{ background: 'var(--bg-primary)' }}
      >
        {isEmpty ? (
          /* ── Gemini-style empty state ── */
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              gap: 40,
              background: 'var(--bg-primary)',
              padding: '0 24px',
            }}
          >
            {/* Free-floating greeting — no box, no border */}
            <p
              style={{
                fontSize: 28,
                fontWeight: 500,
                color: 'var(--text-primary)',
                textAlign: 'center',
                lineHeight: 1.3,
                animation: 'fadeInUp 0.4s ease-out both',
              }}
            >
              Hej, {supplierName ?? 'välkommen'}
            </p>

            {/* Input centered in page */}
            <div
              style={{
                position: 'relative',
                width: '100%',
                maxWidth: 580,
                animation: 'fadeInUp 0.4s ease-out 0.12s both',
              }}
            >
              {/* Animated blue glow behind input */}
              <div
                aria-hidden
                className="gemini-glow"
                style={{
                  position: 'absolute',
                  top: '50%',
                  left: '50%',
                  width: 700,
                  height: 500,
                  pointerEvents: 'none',
                  zIndex: 0,
                }}
              />
              <div style={{ position: 'relative', zIndex: 1 }}>
                {inputBar}
              </div>
            </div>

            {/* Hint text */}
            <p
              style={{
                fontSize: 11,
                color: 'var(--text-muted)',
                textAlign: 'center',
                marginTop: -24,
                animation: 'fadeInUp 0.4s ease-out 0.18s both',
              }}
            >
              Enter för att skicka · Shift+Enter för ny rad
            </p>

            {/* Recent saved insights */}
            <RecentInsightsRow onSendMessage={sendMessage} />
          </div>
        ) : (
          /* ── Active conversation ── */
          <>
            {/* Ny chatt button */}
            <div className="shrink-0 flex justify-end" style={{ padding: '8px 24px 0' }}>
              <button
                type="button"
                onClick={resetChat}
                className="inline-flex items-center gap-1.5 text-xs text-theme-muted hover:text-theme-body transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50 rounded px-2 py-1"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24" aria-hidden>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
                Ny chatt
              </button>
            </div>

            {/* Scrollable messages */}
            <div
              className="flex-1 min-h-0 overflow-y-auto scrollbar-thin"
              style={{ paddingBottom: 8 }}
            >
              <div
                style={{
                  maxWidth: 720,
                  margin: '0 auto',
                  padding: '24px 24px 0',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 16,
                }}
              >
                {messages.map(msg =>
                  msg.role === 'user' ? (
                    <div
                      key={msg.id}
                      className="flex justify-end"
                      style={{ animation: 'chatMsgIn 0.2s ease-out both' }}
                    >
                      <p
                        className="text-white"
                        style={{
                          fontSize: 15,
                          background: 'var(--accent)',
                          borderRadius: '20px 20px 4px 20px',
                          padding: '12px 18px',
                          maxWidth: '55%',
                          lineHeight: 1.5,
                        }}
                      >
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
                      onSendMessage={sendMessage}
                    />
                  )
                )}
                <div ref={bottomRef} />
              </div>
            </div>

            {/* Sticky bottom input */}
            <div
              className="shrink-0"
              style={{
                position: 'sticky',
                bottom: 0,
                background: 'var(--bg-primary)',
                padding: '12px 24px 20px',
              }}
            >
              <div style={{ maxWidth: 680, margin: '0 auto' }}>
                {inputBar}
                <p
                  style={{
                    fontSize: 11,
                    color: 'var(--text-muted)',
                    textAlign: 'center',
                    marginTop: 8,
                  }}
                >
                  Enter för att skicka · Shift+Enter för ny rad
                </p>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  )
}
