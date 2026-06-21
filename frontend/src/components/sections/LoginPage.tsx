import { useState } from 'react'
import { api } from '../../api/client'
import type { AuthUser } from '../../api/types'

const DEMO_ACCOUNTS = [
  { email: 'nordic@demo.solvigo',  label: 'Nordic Coffee AB' },
  { email: 'snacks@demo.solvigo',  label: 'Fresh Snacks Ltd' },
  { email: 'home@demo.solvigo',    label: 'Clean Home Co' },
  { email: 'baltic@demo.solvigo',  label: 'Baltic Roasters AB' },
]

const DEMO_PASSWORD = 'demo1234'

interface LoginPageProps {
  onLogin: (user: AuthUser) => void
}

export function LoginPage({ onLogin }: LoginPageProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim() || !password) return
    setError(null)
    setLoading(true)
    try {
      const user = await api.login(email.trim(), password)
      onLogin(user)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  const fillDemo = (demoEmail: string) => {
    setEmail(demoEmail)
    setPassword(DEMO_PASSWORD)
    setError(null)
  }

  return (
    <div className="min-h-screen bg-zinc-50 flex items-center justify-center px-4">
      <div className="w-full max-w-md space-y-6">

        {/* Wordmark */}
        <div className="text-center">
          <div className="flex items-center justify-center gap-2 mb-1">
            <span className="text-brand-500 text-2xl font-bold">◈</span>
            <span className="text-xl font-semibold text-zinc-900 tracking-tight">
              Solvigo Sales Intelligence
            </span>
          </div>
          <p className="text-sm text-zinc-500">Sign in to access your supplier dashboard</p>
        </div>

        {/* Login card */}
        <div className="bg-white rounded-xl border border-zinc-200 shadow-sm p-8">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-zinc-600 mb-1">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="your@email.com"
                required
                disabled={loading}
                className="w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-brand-400 focus:border-transparent disabled:opacity-50"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-600 mb-1">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                disabled={loading}
                className="w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-brand-400 focus:border-transparent disabled:opacity-50"
              />
            </div>

            {error && (
              <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading || !email.trim() || !password}
              className="w-full bg-brand-500 hover:bg-brand-600 text-white rounded-lg px-4 py-2.5 text-sm font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading && (
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              )}
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>

        {/* Demo accounts */}
        <div className="bg-white rounded-xl border border-zinc-200 shadow-sm p-6">
          <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
            Demo accounts — password: <span className="font-mono text-zinc-700">{DEMO_PASSWORD}</span>
          </p>
          <div className="space-y-2">
            {DEMO_ACCOUNTS.map(account => (
              <button
                key={account.email}
                type="button"
                onClick={() => fillDemo(account.email)}
                disabled={loading}
                className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg border border-zinc-100 hover:border-brand-200 hover:bg-brand-50 text-left transition-colors group disabled:opacity-40"
              >
                <div>
                  <p className="text-sm font-medium text-zinc-800 group-hover:text-brand-700">
                    {account.label}
                  </p>
                  <p className="text-xs text-zinc-400 font-mono">{account.email}</p>
                </div>
                <span className="text-xs text-zinc-300 group-hover:text-brand-400 shrink-0">
                  use →
                </span>
              </button>
            ))}
          </div>
        </div>

        <p className="text-center text-xs text-zinc-400">
          All data grounded via MCP analytics layer · No mock data
        </p>
      </div>
    </div>
  )
}
