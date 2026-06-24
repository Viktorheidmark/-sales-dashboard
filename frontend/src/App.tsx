import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { api } from './api/client'
import type { AuthUser } from './api/types'
import { AppShell } from './components/layout/AppShell'
import { LoginPage } from './components/sections/LoginPage'
import { OverviewPage } from './pages/OverviewPage'
import { AssistantPage } from './pages/AssistantPage'
import { InsightsPage } from './pages/InsightsPage'

type AuthState = 'loading' | 'unauthenticated' | 'authenticated'

export default function App() {
  const [authState, setAuthState] = useState<AuthState>('loading')
  const [user, setUser] = useState<AuthUser | null>(null)

  // Bootstrap session on mount
  useEffect(() => {
    api.me()
      .then(u => {
        setUser(u)
        setAuthState('authenticated')
      })
      .catch(() => setAuthState('unauthenticated'))
  }, [])

  // Return to login on session expiry from any API call
  useEffect(() => {
    const handler = () => {
      setUser(null)
      setAuthState('unauthenticated')
    }
    window.addEventListener('auth:expired', handler)
    return () => window.removeEventListener('auth:expired', handler)
  }, [])

  const handleLogin = (u: AuthUser) => {
    setUser(u)
    setAuthState('authenticated')
  }

  const handleLogout = async () => {
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
    <BrowserRouter
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <Routes>
        <Route element={<AppShell supplierName={user.supplier_name} onLogout={handleLogout} />}>
          <Route path="/" element={<OverviewPage user={user} />} />
          <Route path="/assistant" element={<AssistantPage user={user} />} />
          <Route path="/insights" element={<InsightsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
