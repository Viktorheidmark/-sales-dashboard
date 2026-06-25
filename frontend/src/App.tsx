import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { api } from './api/client'
import type { AuthUser } from './api/types'
import { AppShell } from './components/layout/AppShell'
import { LoginPage } from './components/sections/LoginPage'
import { OverviewPage } from './pages/OverviewPage'
import { AssistantPage } from './pages/AssistantPage'
import { ProductsPage } from './pages/ProductsPage'
import { InsightsPage } from './pages/InsightsPage'
import { ChatStateProvider } from './context/ChatStateContext'
import { TenantBrandingProvider } from './context/TenantBrandingContext'
import { applyTenantTheme, getTenantBranding, resetTenantTheme } from './theme/tenantBranding'

type AuthState = 'loading' | 'unauthenticated' | 'authenticated'

export default function App() {
  const [authState, setAuthState] = useState<AuthState>('loading')
  const [user, setUser] = useState<AuthUser | null>(null)

  // Bootstrap session on mount — apply tenant theme immediately on restore
  useEffect(() => {
    api.me()
      .then(u => {
        applyTenantTheme(getTenantBranding(u.supplier_name))
        setUser(u)
        setAuthState('authenticated')
      })
      .catch(() => setAuthState('unauthenticated'))
  }, [])

  // Return to login on session expiry from any API call
  useEffect(() => {
    const handler = () => {
      resetTenantTheme()
      setUser(null)
      setAuthState('unauthenticated')
    }
    window.addEventListener('auth:expired', handler)
    return () => window.removeEventListener('auth:expired', handler)
  }, [])

  const handleLogin = (u: AuthUser) => {
    applyTenantTheme(getTenantBranding(u.supplier_name))
    setUser(u)
    setAuthState('authenticated')
  }

  const handleLogout = async () => {
    resetTenantTheme()
    await api.logout().catch(() => {})
    setUser(null)
    setAuthState('unauthenticated')
  }

  // Loading state (checking session)
  if (authState === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-workspace">
        <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  // Unauthenticated
  if (authState === 'unauthenticated' || !user) {
    return <LoginPage onLogin={handleLogin} />
  }

  // Authenticated app
  return (
    <TenantBrandingProvider user={user}>
      <ChatStateProvider>
        <BrowserRouter
          future={{
            v7_startTransition: true,
            v7_relativeSplatPath: true,
          }}
        >
          <Routes>
            <Route element={<AppShell supplierName={user.supplier_name} onLogout={handleLogout} />}>
              <Route path="/" element={<OverviewPage user={user} />} />
              <Route path="/products" element={<ProductsPage user={user} />} />
              <Route path="/assistant" element={<AssistantPage user={user} />} />
              <Route path="/insights" element={<InsightsPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ChatStateProvider>
    </TenantBrandingProvider>
  )
}
