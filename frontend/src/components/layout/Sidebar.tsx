import { NavLink, useLocation } from 'react-router-dom'
import { ThemeToggle } from '../ui/ThemeToggle'
import { useChatState } from '../../context/ChatStateContext'

interface SidebarProps {
  supplierName: string
  onLogout: () => void
  onNavigate?: () => void
}

const NAV_ITEMS = [
  {
    to: '/',
    label: 'Översikt',
    icon: (
      <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.6} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l9-9 9 9M5 10v10a1 1 0 001 1h4v-6h4v6h4a1 1 0 001-1V10" />
      </svg>
    ),
  },
  {
    to: '/assistant',
    label: 'Analysassistent',
    icon: (
      <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.6} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h8M8 14h5M21 12a8 8 0 01-11.5 7.2L4 21l1.8-5.5A8 8 0 1121 12z" />
      </svg>
    ),
  },
  {
    to: '/insights',
    label: 'Sparade insikter',
    icon: (
      <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.6} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 3h14a1 1 0 011 1v17l-7-4-7 4V4a1 1 0 011-1z" />
      </svg>
    ),
  },
]

export function Sidebar({ supplierName, onLogout, onNavigate }: SidebarProps) {
  const initial = supplierName ? supplierName.charAt(0).toUpperCase() : '?'
  const location = useLocation()
  const { hasMessages, onNewChat } = useChatState()
  const isAssistant = location.pathname === '/assistant'
  const showNewChat = isAssistant && hasMessages && onNewChat != null

  return (
    <div className="flex h-full flex-col bg-sidebar select-none border-r border-sidebar-border">
      {/* Brand */}
      <div className="px-5 py-6 border-b border-sidebar-border">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-brand-500/15 border border-brand-500/25 flex items-center justify-center shrink-0">
            <span className="text-brand-600 dark:text-brand-400 text-base font-bold leading-none">◈</span>
          </div>
          <div>
            <div className="text-sm font-semibold text-theme-heading leading-tight tracking-tight">Solvigo</div>
            <div className="text-[10px] font-medium tracking-[0.18em] uppercase text-theme-muted leading-tight mt-0.5">
              Sales Intelligence
            </div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="px-3 py-5 space-y-0.5">
        <p className="text-[10px] font-semibold text-theme-faint uppercase tracking-[0.16em] px-3 mb-3">
          Navigering
        </p>
        {NAV_ITEMS.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            onClick={onNavigate}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/40 ${
                isActive
                  ? 'bg-brand-500/10 text-theme-heading border-l-2 border-brand-500 pl-[10px]'
                  : 'text-theme-muted hover:text-theme-strong hover:bg-[var(--surface-hover)] border-l-2 border-transparent pl-[10px]'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <span className={isActive ? 'text-brand-600 dark:text-brand-400' : 'text-theme-faint'}>{item.icon}</span>
                {item.label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* New Chat button — only on /assistant with active messages */}
      {showNewChat && (
        <div className="px-4 pb-2">
          <NewChatButton onClick={() => { onNewChat(); onNavigate?.() }} />
        </div>
      )}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Account */}
      <div className="px-4 py-5 border-t border-sidebar-border">
        <p className="text-[10px] font-semibold text-theme-faint uppercase tracking-[0.14em] px-1 mb-2">
          Aktiv leverantör
        </p>
        <div className="surface-inset flex items-center gap-2.5 px-3 py-2.5 mb-3">
          <div className="w-8 h-8 rounded-full bg-workspace-elevated border border-workspace-border flex items-center justify-center shrink-0 text-xs font-semibold text-brand-600 dark:text-brand-400">
            {initial}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-theme-heading truncate leading-snug" title={supplierName}>
              {supplierName || '—'}
            </p>
            <p className="text-[10px] text-theme-muted leading-snug mt-0.5">Leverantörsvy · isolerad data</p>
          </div>
        </div>
        <div className="flex items-center justify-between px-1 mb-3">
          <button
            onClick={onLogout}
            className="flex items-center gap-2 text-xs font-medium text-theme-muted hover:text-theme-body transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/40 rounded px-2 py-1.5"
          >
            <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            Logga ut
          </button>
          <ThemeToggle compact />
        </div>
      </div>
    </div>
  )
}

function NewChatButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full flex items-center gap-2 rounded-lg text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/40"
      style={{
        padding: '10px 12px',
        border: '1px solid var(--border-color)',
        background: 'transparent',
        color: 'var(--text-secondary)',
        fontSize: 13,
        fontWeight: 500,
        cursor: 'pointer',
      }}
      onMouseEnter={e => {
        const el = e.currentTarget
        el.style.background = 'var(--bg-secondary)'
        el.style.color = 'var(--text-primary)'
      }}
      onMouseLeave={e => {
        const el = e.currentTarget
        el.style.background = 'transparent'
        el.style.color = 'var(--text-secondary)'
      }}
    >
      <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
      </svg>
      Ny chatt
    </button>
  )
}
