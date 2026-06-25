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
    to: '/products',
    label: 'Produkter',
    icon: (
      <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.6} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
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
    <div className="tenant-sidebar flex h-full flex-col select-none relative overflow-hidden">
      {/* Brand header */}
      <div className="tenant-sidebar-brand px-5 py-6">
        <div className="flex items-center gap-3">
          <div className="tenant-sidebar-brand-mark w-9 h-9 rounded-lg flex items-center justify-center shrink-0">
            <span className="tenant-sidebar-brand-icon text-base font-bold leading-none">◈</span>
          </div>
          <div>
            <div className="tenant-sidebar-brand-title text-sm font-semibold leading-tight tracking-tight">Solvigo</div>
            <div className="tenant-sidebar-brand-sub text-[10px] font-medium tracking-[0.18em] uppercase leading-tight mt-0.5">
              Sales Intelligence
            </div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="px-3 py-5 space-y-0.5">
        <p className="tenant-sidebar-section-label">Navigering</p>
        {NAV_ITEMS.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            onClick={onNavigate}
            className={({ isActive }) =>
              `sidebar-nav-link focus:outline-none ${isActive ? 'is-active' : ''}`
            }
          >
            <span className="sidebar-nav-icon">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* New Chat button — only on /assistant with active messages */}
      {showNewChat && (
        <div className="px-4 pb-2">
          <button
            type="button"
            onClick={() => {
              onNewChat?.()
              onNavigate?.()
            }}
            className="tenant-sidebar-new-chat focus:outline-none"
          >
            <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            Ny chatt
          </button>
        </div>
      )}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Supplier card + account section */}
      <div className="tenant-sidebar-footer px-4 py-5">
        <p className="tenant-sidebar-section-label px-1 mb-2.5">Aktiv leverantör</p>

        <div className="tenant-supplier-card flex items-center gap-3 px-3 py-3 mb-3">
          <div className="tenant-supplier-avatar">{initial}</div>
          <div className="min-w-0 flex-1">
            <p
              className="tenant-sidebar-supplier-name text-sm font-semibold truncate leading-snug"
              title={supplierName}
            >
              {supplierName || '—'}
            </p>
            <p className="tenant-sidebar-supplier-sub text-[10px] leading-snug mt-0.5">
              Leverantörsvy · Isolerad data
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between px-1">
          <button
            type="button"
            onClick={onLogout}
            className="tenant-sidebar-logout focus:outline-none"
          >
            <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            Logga ut
          </button>
          <ThemeToggle compact className="sidebar-theme-toggle" />
        </div>
      </div>
    </div>
  )
}
