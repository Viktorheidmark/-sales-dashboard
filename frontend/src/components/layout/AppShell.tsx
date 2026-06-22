import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'

interface AppShellProps {
  supplierName: string
  onLogout: () => void
}

export function AppShell({ supplierName, onLogout }: AppShellProps) {
  const [drawerOpen, setDrawerOpen] = useState(false)

  return (
    <div className="min-h-screen bg-workspace">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex md:fixed md:inset-y-0 md:left-0 md:w-60 z-30">
        <Sidebar supplierName={supplierName} onLogout={onLogout} />
      </aside>

      {/* Mobile top bar */}
      <div className="md:hidden sticky top-0 z-30 flex items-center justify-between bg-sidebar border-b border-sidebar-border px-4 py-3">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-md bg-brand-500/20 border border-brand-500/30 flex items-center justify-center">
            <span className="text-brand-400 text-sm font-bold leading-none">◈</span>
          </div>
          <span className="text-sm font-semibold text-slate-100 tracking-tight">Solvigo</span>
        </div>
        <button
          onClick={() => setDrawerOpen(true)}
          className="text-slate-400 hover:text-slate-200 p-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50 rounded"
          aria-label="Öppna meny"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
      </div>

      {/* Mobile drawer */}
      {drawerOpen && (
        <div className="md:hidden fixed inset-0 z-40">
          <div className="absolute inset-0 bg-black/60" onClick={() => setDrawerOpen(false)} aria-hidden />
          <div className="absolute inset-y-0 left-0 w-64 border-r border-sidebar-border">
            <Sidebar
              supplierName={supplierName}
              onLogout={onLogout}
              onNavigate={() => setDrawerOpen(false)}
            />
          </div>
        </div>
      )}

      {/* Content */}
      <main className="md:pl-60">
        <div className="max-w-screen-xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
