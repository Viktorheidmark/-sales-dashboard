import { NavLink } from 'react-router-dom'

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

  return (
    <div className="flex h-full flex-col bg-sidebar select-none border-r border-sidebar-border">
      {/* Brand */}
      <div className="px-5 py-6 border-b border-sidebar-border">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-brand-500/15 border border-brand-500/25 flex items-center justify-center shrink-0">
            <span className="text-brand-400 text-base font-bold leading-none">◈</span>
          </div>
          <div>
            <div className="text-sm font-semibold text-slate-100 leading-tight tracking-tight">Solvigo</div>
            <div className="text-[10px] font-medium tracking-[0.18em] uppercase text-slate-500 leading-tight mt-0.5">
              Sales Intelligence
            </div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-5 space-y-0.5">
        <p className="text-[10px] font-semibold text-slate-600 uppercase tracking-[0.16em] px-3 mb-3">
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
                  ? 'bg-brand-500/10 text-slate-100 border-l-2 border-brand-500 pl-[10px]'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.03] border-l-2 border-transparent pl-[10px]'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <span className={isActive ? 'text-brand-400' : 'text-slate-500'}>{item.icon}</span>
                {item.label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Account */}
      <div className="px-4 py-5 border-t border-sidebar-border">
        <div className="surface-inset flex items-center gap-2.5 px-3 py-2.5 mb-3">
          <div className="w-8 h-8 rounded-full bg-workspace-elevated border border-workspace-border flex items-center justify-center shrink-0 text-xs font-semibold text-slate-200">
            {initial}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium text-slate-200 truncate leading-snug" title={supplierName}>
              {supplierName || '—'}
            </p>
            <p className="text-[10px] text-slate-500 leading-snug mt-0.5">Leverantörsvy</p>
          </div>
        </div>
        <button
          onClick={onLogout}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium text-slate-500 hover:text-slate-300 hover:bg-white/[0.03] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/40"
        >
          <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
          Logga ut
        </button>
      </div>
    </div>
  )
}
