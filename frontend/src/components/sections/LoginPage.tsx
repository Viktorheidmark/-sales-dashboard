import { useState } from 'react'
import { api } from '../../api/client'
import type { AuthUser } from '../../api/types'
import { ThemeToggle } from '../ui/ThemeToggle'

const DEMO_ACCOUNTS = [
  { email: 'arla@demo.solvigo',          label: 'Arla Sverige' },
  { email: 'cocacola@demo.solvigo',      label: 'Coca-Cola Europacific Partners Sverige' },
  { email: 'orkla@demo.solvigo',         label: 'Orkla Sverige' },
  { email: 'skanemejerier@demo.solvigo', label: 'Skånemejerier' },
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
    } catch {
      setError('Felaktiga inloggningsuppgifter. Kontrollera e-post och lösenord.')
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
    <div className="min-h-screen bg-workspace flex flex-col items-center justify-center px-4 py-8 relative">
      <div className="absolute top-4 right-4">
        <ThemeToggle compact />
      </div>

      <div className="w-full max-w-md space-y-6">
        {/* Wordmark */}
        <div className="text-center">
          <div className="flex items-center justify-center gap-2 mb-1">
            <span className="text-brand-600 dark:text-brand-500 text-2xl font-bold">◈</span>
            <span className="text-xl font-semibold text-theme-heading tracking-tight">
              Solvigo Sales Intelligence
            </span>
          </div>
          <p className="text-sm text-theme-muted">Logga in för att se er leverantörsdashboard</p>
        </div>

        {/* Login card */}
        <div className="surface-card p-8">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-theme-muted mb-1">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="your@email.com"
                required
                disabled={loading}
                className="input-field"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-theme-muted mb-1">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                disabled={loading}
                className="input-field"
              />
            </div>

            {error && (
              <p className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading || !email.trim() || !password}
              className="w-full bg-brand-500 hover:bg-brand-600 text-white rounded-lg px-4 py-2.5 text-sm font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50"
            >
              {loading && (
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              )}
              {loading ? 'Loggar in…' : 'Logga in'}
            </button>
          </form>
        </div>

        {/* Demo accounts */}
        <div className="surface-card p-6">
          <p className="text-xs font-semibold text-theme-muted uppercase tracking-wider mb-3">
            Demo accounts — password: <span className="font-mono text-theme-strong">{DEMO_PASSWORD}</span>
          </p>
          <div className="space-y-2">
            {DEMO_ACCOUNTS.map(account => (
              <button
                key={account.email}
                type="button"
                onClick={() => fillDemo(account.email)}
                disabled={loading}
                className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg border border-workspace-border hover:border-brand-500/30 hover:bg-brand-500/5 text-left transition-colors group disabled:opacity-40 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50"
              >
                <div>
                  <p className="text-sm font-medium text-theme-strong group-hover:text-brand-600 dark:group-hover:text-brand-400">
                    {account.label}
                  </p>
                  <p className="text-xs text-theme-faint font-mono">{account.email}</p>
                </div>
                <span className="text-xs text-theme-faint group-hover:text-brand-600 dark:group-hover:text-brand-400 shrink-0">
                  use →
                </span>
              </button>
            ))}
          </div>
        </div>

        <p className="text-center text-xs text-theme-faint">
          Grundat i MCP-analyserad syntetisk demodata
        </p>
      </div>
    </div>
  )
}
