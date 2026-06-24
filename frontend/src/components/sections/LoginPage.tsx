import { useState } from 'react'
import { api } from '../../api/client'
import type { AuthUser } from '../../api/types'
import { ThemeToggle } from '../ui/ThemeToggle'

const DEMO_ACCOUNTS = [
  { email: 'cocacola@demo.solvigo', label: 'Coca-Cola Europacific Partners Sverige' },
  { email: 'pepsico@demo.solvigo', label: 'PepsiCo Northern Europe' },
  { email: 'olw@demo.solvigo', label: 'Orkla Snacks Sverige' },
  { email: 'estrella@demo.solvigo', label: 'Estrella AB' },
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
    <div className="min-h-screen bg-workspace flex flex-col">
      <div className="absolute top-5 right-5 z-10">
        <ThemeToggle compact />
      </div>

      <main className="relative z-[1] flex flex-1 items-center justify-center px-4 py-8 sm:px-6 sm:py-10">
        <div className="w-full max-w-[26rem]">
          <header className="text-center mb-7">
            <div className="inline-flex items-center justify-center gap-2.5 mb-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-workspace-border bg-workspace-surface">
                <span className="text-brand-600 dark:text-brand-500 text-lg font-bold leading-none">◈</span>
              </div>
              <div className="text-left">
                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-theme-muted">
                  Solvigo
                </p>
                <p className="text-base font-semibold text-theme-heading tracking-tight leading-tight">
                  Sales Intelligence
                </p>
              </div>
            </div>
            <h1 className="text-xl font-semibold text-theme-heading tracking-tight leading-snug">
              Leverantörsanalys med datadriven insikt
            </h1>
            <p className="mt-2 text-sm text-theme-muted leading-relaxed">
              Följ försäljning, produkter och marknadsandel per leverantör — isolerat och grundat i verifierad analysdata.
            </p>
          </header>

          <div className="surface-card border-workspace-border px-6 py-6 sm:px-7 sm:py-7">
            <div className="mb-5 pb-5 border-b border-workspace-border/70">
              <h2 className="text-[15px] font-semibold text-theme-heading">Logga in</h2>
              <p className="text-xs text-theme-muted mt-1 leading-relaxed">
                Fortsätt till er leverantörsdashboard
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="login-email" className="block text-xs font-medium text-theme-muted mb-1.5">
                  E-post
                </label>
                <input
                  id="login-email"
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="your@email.com"
                  required
                  disabled={loading}
                  autoComplete="username"
                  className="input-field"
                />
              </div>

              <div>
                <label htmlFor="login-password" className="block text-xs font-medium text-theme-muted mb-1.5">
                  Lösenord
                </label>
                <input
                  id="login-password"
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  disabled={loading}
                  autoComplete="current-password"
                  className="input-field"
                />
              </div>

              {error && (
                <p
                  role="alert"
                  className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 rounded-lg px-3 py-2 leading-snug"
                >
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

          <section className="mt-4 surface-card border-workspace-border px-5 py-5 sm:px-6 sm:py-6">
            <div className="mb-3.5">
              <p className="text-sm font-semibold text-theme-heading">Demoarbetsytor</p>
              <p className="text-xs text-theme-muted mt-0.5 leading-relaxed">
                Välj leverantör — fyller i e-post och lösenord automatiskt
              </p>
            </div>

            <ul className="space-y-2">
              {DEMO_ACCOUNTS.map(account => {
                const selected = email === account.email
                return (
                  <li key={account.email}>
                    <button
                      type="button"
                      onClick={() => fillDemo(account.email)}
                      disabled={loading}
                      className={[
                        'w-full flex items-center gap-3 rounded-lg border px-3.5 py-3 text-left transition-colors',
                        'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50 disabled:opacity-40',
                        selected
                          ? 'border-brand-500/45 bg-brand-500/[0.07]'
                          : 'border-workspace-border bg-workspace-elevated/50 hover:border-brand-500/30 hover:bg-brand-500/[0.04]',
                      ].join(' ')}
                    >
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-workspace-border bg-workspace-surface text-xs font-semibold text-theme-muted">
                        {account.label.charAt(0)}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-medium text-theme-strong leading-snug truncate">
                          {account.label}
                        </span>
                        <span className="block text-[11px] text-theme-faint font-mono truncate mt-0.5">
                          {account.email}
                        </span>
                      </span>
                      {selected && (
                        <span className="shrink-0 text-[10px] font-medium uppercase tracking-wide text-brand-600 dark:text-brand-400">
                          Vald
                        </span>
                      )}
                    </button>
                  </li>
                )
              })}
            </ul>

            <p className="mt-4 pt-3.5 border-t border-workspace-border/70 text-[11px] text-theme-faint">
              Demolösenord: <span className="font-mono text-theme-muted">{DEMO_PASSWORD}</span>
            </p>
          </section>

          <p className="mt-4 text-center text-[11px] text-theme-muted leading-relaxed px-2">
            Demo med syntetisk försäljningsdata. Ingen riktig kunddata visas.
          </p>
        </div>
      </main>
    </div>
  )
}
