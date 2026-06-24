import { useState, useRef, useEffect, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import { api } from '../../api/client'
import type { ChatResponse, DateRange, FollowUpAction, InsightSummary, PriorTurnContext, SourceMeta } from '../../api/types'
import { formatDate } from '../../utils/format'
import { MiniAssistantChart } from '../charts/MiniAssistantChart'
import { DeepDivePanel } from '../charts/DeepDivePanel'
import {
  ANALYTICS_DATA_SOURCE,
  formatSourcePeriod,
  isMarketShareResponse,
  resolveResponseDateRange,
  toolLabelSv,
  visibleResponseLimitations,
} from '../../utils/sourcePresentation'

// ---------------------------------------------------------------------------
// Suggestion cards with icons
// ---------------------------------------------------------------------------

const PROMPT_CARDS = [
  {
    label: '30-dagars utveckling',
    sub: 'Hur har försäljningen utvecklats de senaste 30 dagarna?',
    prompt: 'Hur har försäljningen utvecklats de senaste 30 dagarna?',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941" />
      </svg>
    ),
    iconColor: 'text-blue-500',
    iconBg: 'bg-blue-50 dark:bg-blue-500/10',
  },
  {
    label: 'Produkt i nedgång',
    sub: 'Vilken produkt har tappat mest de senaste 30 dagarna?',
    prompt: 'Vilken produkt har tappat mest de senaste 30 dagarna?',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
      </svg>
    ),
    iconColor: 'text-amber-500',
    iconBg: 'bg-amber-50 dark:bg-amber-500/10',
  },
  {
    label: 'Starkaste region',
    sub: 'Vilken region genererar mest intäkter?',
    prompt: 'Vilken region genererar mest intäkter?',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
      </svg>
    ),
    iconColor: 'text-emerald-500',
    iconBg: 'bg-emerald-50 dark:bg-emerald-500/10',
  },
  {
    label: 'Marknadsandel',
    sub: 'Hur stor är vår marknadsandel?',
    prompt: 'Hur stor är vår marknadsandel?',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6a7.5 7.5 0 107.5 7.5h-7.5V6z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 10.5H21A7.5 7.5 0 0013.5 3v7.5z" />
      </svg>
    ),
    iconColor: 'text-purple-500',
    iconBg: 'bg-purple-50 dark:bg-purple-500/10',
  },
]

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

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
    <div className={isSecondary ? 'opacity-95' : ''}>
      {chart.title && (
        <p className={`font-semibold text-theme-body mb-1 leading-snug ${isSecondary ? 'text-[11px]' : 'text-xs'}`}>
          {chart.title}
        </p>
      )}
      {chart.description && (
        <p className={`text-theme-muted mb-2 leading-relaxed ${isSecondary ? 'text-[11px]' : 'text-xs'}`}>
          {chart.description}
        </p>
      )}
      <div className={`rounded-lg border border-workspace-border bg-workspace-muted/50 px-3 py-2 ${isSecondary ? 'max-w-sm' : ''}`}>
        <MiniAssistantChart chart={chart} supplierName={supplierName} compact={isSecondary} />
      </div>
      {chart.stability_note && (
        <p className="mt-1.5 text-[11px] text-theme-muted leading-snug italic">{chart.stability_note}</p>
      )}
      {chart.period_note && (
        <p className="mt-1.5 text-[11px] text-theme-muted leading-snug">{chart.period_note}</p>
      )}
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
  onSendMessage: (text: string, followUpAction?: FollowUpAction) => void
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
        className="self-start max-w-[80%] bg-white dark:bg-workspace-elevated border border-[#F1F5F9] dark:border-workspace-border rounded-[18px] rounded-tl-[4px] px-5 py-4"
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
        className="self-start max-w-[80%] bg-white dark:bg-workspace-elevated border border-[#F1F5F9] dark:border-workspace-border rounded-[18px] rounded-tl-[4px] px-5 py-4 space-y-1"
        style={{ animation: 'chatMsgIn 0.25s ease-out both' }}
      >
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
      <article
        className="self-start max-w-[80%] bg-white dark:bg-workspace-elevated border border-[#F1F5F9] dark:border-workspace-border rounded-[18px] rounded-tl-[4px] px-5 py-4"
        style={{ animation: 'chatMsgIn 0.25s ease-out both' }}
      >
        <p className="text-[15px] text-theme-muted leading-relaxed">{msg.error}</p>
      </article>
    )
  }

  const r = msg.response!
  const isGrounded = r.tool_calls.length > 0
  const displayLimitations = visibleResponseLimitations(r.limitations, r)

  return (
    <article
      className="self-start max-w-[80%] bg-white dark:bg-workspace-elevated border border-[#F1F5F9] dark:border-workspace-border rounded-[18px] rounded-tl-[4px] px-5 py-4 space-y-5"
      style={{ animation: 'chatMsgIn 0.25s ease-out both' }}
    >
      <div className="text-[15px] text-theme-body leading-[1.75]">
        <ReactMarkdown components={markdownComponents}>
          {msg.content}
        </ReactMarkdown>
      </div>

      {!r.chart && r.tool_calls.includes('get_sales_over_time') && !r.deep_dive && (
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

      {(r.follow_up_actions ?? []).length > 0 && (
        <div className="flex flex-wrap gap-2 pt-1">
          {r.follow_up_actions!.map((action) => (
            <button
              key={action.label}
              onClick={() => onSendMessage(action.message, action)}
              className="text-xs px-2.5 py-1 rounded-full border border-workspace-border bg-workspace-surface text-theme-body hover:border-brand-400/60 hover:text-brand-600 dark:hover:text-brand-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50"
            >
              {action.label}
            </button>
          ))}
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
    <div className="mt-6" style={{ animation: 'greetingIn 0.5s ease-out 0.2s both' }}>
      <p className="text-[11px] uppercase tracking-widest text-[#9CA3AF] font-medium mb-2.5 text-center">
        Senaste analyser
      </p>
      <div className="flex flex-wrap justify-center gap-2">
        {insights.map(insight => (
          <button
            key={insight.id}
            onClick={() => onSendMessage(insight.question)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white dark:bg-workspace-elevated border border-[#E2E8F0] dark:border-workspace-border text-[12px] text-[#374151] dark:text-theme-body hover:border-[#3B82F6] hover:text-[#3B82F6] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50"
          >
            <svg className="w-3 h-3 opacity-50 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="truncate max-w-[200px]">
              {insight.question.length > 40 ? insight.question.slice(0, 40) + '…' : insight.question}
            </span>
          </button>
        ))}
      </div>
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

  const sendMessage = async (text: string, followUpAction?: FollowUpAction) => {
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
          follow_up_action: followUpAction?.action ? followUpAction : undefined,
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

  const resetChat = () => {
    abortRef.current?.abort()
    abortRef.current = null
    setMessages([])
    setInput('')
    setLoading(false)
    inputRef.current?.focus()
  }

  const isEmpty = messages.length === 0
  const showPresence = isEmpty && !loading && input.trim().length === 0
  const hasConversation = messages.length > 0 || loading
  const placeholder = supplierName
    ? `Fråga om ${supplierName}s försäljning, produkter eller marknadsandel…`
    : 'Fråga om försäljning, produkter eller marknadsandel…'

  return (
    <>
      {/* Keyframe animations injected once */}
      <style>{`
        @keyframes greetingIn {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes chatMsgIn {
          from { opacity: 0; transform: translateY(8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      <div className="flex flex-col flex-1 min-h-0 w-full max-w-3xl lg:max-w-[60rem] xl:max-w-[62.5rem] mx-auto">
        {hasConversation && (
          <div className="shrink-0 flex justify-end pb-2">
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
        )}

        {/* Conversation workspace */}
        <div className="flex-1 min-h-0 overflow-y-auto scrollbar-thin">
          {isEmpty ? (
            /* ── Empty / greeting state ── */
            <div
              className="flex flex-col min-h-full px-2 py-10 sm:py-16 relative"
              style={{
                background: 'radial-gradient(ellipse at 50% 40%, rgba(59,130,246,0.06) 0%, rgba(248,250,252,0) 70%)',
              }}
            >
              {/* Greeting */}
              <div
                className="w-full text-center mb-10"
                style={{ animation: 'greetingIn 0.5s ease-out both' }}
              >
                <p style={{ fontSize: 18, fontWeight: 400, color: '#6B7280', lineHeight: 1.3 }}>
                  Hej,
                </p>
                <p style={{ fontSize: 32, fontWeight: 700, color: '#0F172A', lineHeight: 1.2, marginBottom: 8 }}>
                  {supplierName ?? 'välkommen'}
                </p>
                <p style={{ fontSize: 16, fontWeight: 400, color: '#6B7280' }}>
                  Vad vill du analysera idag?
                </p>
              </div>

              {/* Suggestion cards */}
              <div
                className="w-full grid grid-cols-1 sm:grid-cols-2 gap-3"
                style={{ animation: 'greetingIn 0.5s ease-out 0.08s both' }}
              >
                {PROMPT_CARDS.map(card => (
                  <button
                    key={card.prompt}
                    onClick={() => sendMessage(card.prompt)}
                    disabled={loading}
                    className="group relative text-left flex items-start gap-4 rounded-xl px-5 py-4 transition-all duration-200 disabled:opacity-50"
                    style={{
                      background: 'white',
                      border: '1px solid #E2E8F0',
                      borderRadius: 12,
                    }}
                    onMouseEnter={e => {
                      const el = e.currentTarget
                      el.style.transform = 'translateY(-2px)'
                      el.style.boxShadow = '0 4px 12px rgba(0,0,0,0.08)'
                      el.style.borderColor = '#3B82F6'
                    }}
                    onMouseLeave={e => {
                      const el = e.currentTarget
                      el.style.transform = ''
                      el.style.boxShadow = ''
                      el.style.borderColor = '#E2E8F0'
                    }}
                  >
                    {/* Icon */}
                    <span className={`shrink-0 flex items-center justify-center w-9 h-9 rounded-lg mt-0.5 ${card.iconBg} ${card.iconColor}`}>
                      {card.icon}
                    </span>

                    {/* Text */}
                    <span className="flex-1 min-w-0">
                      <span className="block text-sm font-semibold text-[#0F172A] dark:text-theme-heading leading-snug">
                        {card.label}
                      </span>
                      <span className="block mt-1 text-xs text-[#6B7280] dark:text-theme-muted leading-relaxed">
                        {card.sub}
                      </span>
                    </span>

                    {/* Arrow appears on hover */}
                    <span
                      className="shrink-0 self-center text-[#3B82F6] opacity-0 group-hover:opacity-100 transition-opacity duration-200 text-sm font-medium"
                      aria-hidden
                    >
                      →
                    </span>
                  </button>
                ))}
              </div>

              {/* Recent insights */}
              <RecentInsightsRow onSendMessage={sendMessage} />

              {/* Presence indicator */}
              <div
                className="flex-1 flex items-end justify-center min-h-[4.5rem] pt-10 pb-2"
                aria-hidden={!showPresence}
              >
                {showPresence && (
                  <div className="chat-presence">
                    <span className="chat-presence-outer" />
                    <span className="chat-presence-mid" />
                    <span className="chat-presence-center" />
                  </div>
                )}
              </div>
            </div>
          ) : (
            /* ── Conversation messages ── */
            <div className="py-6 sm:py-8 space-y-6">
              {messages.map(msg =>
                msg.role === 'user' ? (
                  /* User bubble */
                  <div
                    key={msg.id}
                    className="flex justify-end"
                    style={{ animation: 'chatMsgIn 0.2s ease-out both' }}
                  >
                    <p
                      className="text-sm font-medium text-white leading-snug px-4 py-2.5"
                      style={{
                        background: '#3B82F6',
                        borderRadius: '18px 18px 4px 18px',
                        maxWidth: '60%',
                      }}
                    >
                      {msg.content}
                    </p>
                  </div>
                ) : (
                  /* Assistant bubble */
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
          )}
        </div>

        {/* ── Composer / Input ── */}
        <div className="shrink-0 pt-4 pb-2">
          <div
            className="relative flex items-center bg-white dark:bg-workspace-elevated transition-all"
            style={{
              border: '1.5px solid #E2E8F0',
              borderRadius: 14,
            }}
            onFocusCapture={e => {
              const el = e.currentTarget
              el.style.borderColor = '#3B82F6'
              el.style.boxShadow = '0 0 0 3px rgba(59,130,246,0.1)'
            }}
            onBlurCapture={e => {
              if (!e.currentTarget.contains(e.relatedTarget as Node)) {
                const el = e.currentTarget
                el.style.borderColor = '#E2E8F0'
                el.style.boxShadow = ''
              }
            }}
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              rows={2}
              disabled={loading}
              className="flex-1 resize-none bg-transparent px-5 py-4 pr-14 text-[15px] text-theme-strong placeholder:text-theme-muted focus:outline-none disabled:opacity-50 scrollbar-thin leading-relaxed"
              style={{ borderRadius: 14, minHeight: 56 }}
            />
            <button
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || loading}
              className="absolute right-3 bottom-3 flex items-center justify-center text-white transition-all duration-150 disabled:opacity-35 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
              style={{
                width: 40,
                height: 40,
                borderRadius: '50%',
                background: '#3B82F6',
              }}
              onMouseEnter={e => {
                if (!e.currentTarget.disabled) {
                  e.currentTarget.style.background = '#2563EB'
                  e.currentTarget.style.transform = 'scale(1.05)'
                }
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = '#3B82F6'
                e.currentTarget.style.transform = ''
              }}
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
    </>
  )
}
