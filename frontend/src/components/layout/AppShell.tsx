import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { Sidebar } from './Sidebar'

interface AppShellProps {
  supplierName: string
  onLogout: () => void
}

export function AppShell({ supplierName, onLogout }: AppShellProps) {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const location = useLocation()
  const isFullBleed = location.pathname === '/assistant'

  return (
    <div className="min-h-screen bg-workspace max-md:block md:grid md:grid-cols-[240px_minmax(0,1fr)]">
      {/* Desktop sidebar */}
      <aside className="hidden md:block sticky top-0 h-screen z-30">
        <Sidebar supplierName={supplierName} onLogout={onLogout} />
      </aside>

      {/* Mobile top bar */}
      <div className="md:hidden sticky top-0 z-30 flex items-center justify-between bg-sidebar border-b border-sidebar-border px-4 py-3">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-md bg-brand-500/20 border border-brand-500/30 flex items-center justify-center">
            <span className="text-brand-400 text-sm font-bold leading-none">◈</span>
          </div>
          <span className="text-sm font-semibold text-theme-heading tracking-tight">Solvigo</span>
        </div>
        <button
          onClick={() => setDrawerOpen(true)}
          className="text-theme-muted hover:text-theme-strong p-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50 rounded"
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
      <main
        className="min-w-0 w-full"
        style={isFullBleed ? { display: 'flex', flexDirection: 'column', minHeight: '100vh' } : undefined}
      >
        {isFullBleed ? (
          <Outlet />
        ) : (
          <>
            {/* Premium tenant ambient canvas — edge fades + header glow */}
            <div className="workspace-ambient-canvas" aria-hidden>
              <div className="workspace-ambient-edge workspace-ambient-edge-left" />
              <div className="workspace-ambient-edge workspace-ambient-edge-right" />
              <div className="workspace-ambient-header-glow" />
              <div className="workspace-ambient-center-veil" />
              <div className="workspace-ambient-grid" />
            </div>

            {/* Content on top of ambient */}
            <div className="dashboard-content-shell">
              <Outlet />
            </div>
          </>
        )}
      </main>
    </div>
  )
}
