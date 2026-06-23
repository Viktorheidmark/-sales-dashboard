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

      <div
        className="pointer-events-none absolute inset-0 bg-workspace-canvas/40 dark:bg-workspace-canvas/25"
        aria-hidden
      />

      <main className="relative z-[1] flex flex-1 items-center justify-center px-4 py-10 sm:px-6 sm:py-12">
        <div className="w-full max-w-[32rem]">
          <header className="text-center mb-8 sm:mb-9">
            <div className="inline-flex items-center justify-center gap-3 mb-5">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-workspace-border bg-workspace-surface">
                <span className="text-brand-600 dark:text-brand-500 text-xl font-bold leading-none">◈</span>
              </div>
              <div className="text-left">
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-theme-muted">
                  Solvigo
                </p>
                <p className="text-lg font-semibold text-theme-heading tracking-tight">
                  Sales Intelligence
                </p>
              </div>
            </div>
            <h1 className="text-xl sm:text-2xl font-semibold text-theme-heading tracking-tight leading-snug">
              Leverantörsanalys med datadriven insikt
            </h1>
            <p className="mt-2.5 text-sm text-theme-muted leading-relaxed max-w-md mx-auto">
              Följ försäljning, produkter och marknadsandel per leverantör — isolerat och grundat i verifierad analysdata.
            </p>
          </header>

          <div className="surface-card border-workspace-border/80 px-7 py-7 sm:px-8 sm:py-8">
            <div className="mb-6">
              <h2 className="text-base font-semibold text-theme-heading">Logga in</h2>
              <p className="text-sm text-theme-muted mt-1">Fortsätt till er leverantörsdashboard</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-theme-muted mb-1.5">
                  E-post
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
                <label className="block text-xs font-medium text-theme-muted mb-1.5">
                  Lösenord
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

          <section className="mt-5 surface-card border-workspace-border/80 px-6 py-6 sm:px-7 sm:py-7">
            <div className="flex items-baseline justify-between gap-3 mb-4">
              <div>
                <p className="text-sm font-semibold text-theme-heading">Välj demoarbetsyta</p>
                <p className="text-xs text-theme-muted mt-0.5">Klicka för att fylla i inloggningen</p>
              </div>
              <p className="text-[11px] text-theme-faint shrink-0">
                Lösenord: <span className="font-mono text-theme-muted">{DEMO_PASSWORD}</span>
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {DEMO_ACCOUNTS.map(account => {
                const selected = email === account.email
                return (
                  <button
                    key={account.email}
                    type="button"
                    onClick={() => fillDemo(account.email)}
                    disabled={loading}
                    className={[
                      'flex flex-col items-start gap-2 rounded-xl border px-4 py-3.5 text-left transition-colors',
                      'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50 disabled:opacity-40',
                      selected
                        ? 'border-brand-500/40 bg-brand-500/[0.06]'
                        : 'border-workspace-border bg-workspace-elevated/60 hover:border-brand-500/25 hover:bg-brand-500/[0.04]',
                    ].join(' ')}
                  >
                    <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-workspace-border bg-workspace-surface text-xs font-semibold text-theme-muted">
                      {account.label.charAt(0)}
                    </span>
                    <span className="min-w-0">
                      <span className="block text-sm font-medium text-theme-strong leading-snug">
                        {account.label}
                      </span>
                      <span className="block text-[11px] text-theme-faint font-mono truncate mt-0.5">
                        {account.email}
                      </span>
                    </span>
                  </button>
                )
              })}
            </div>
          </section>

          <p className="mt-5 text-center text-[11px] text-theme-faint leading-relaxed">
            Demo med syntetisk försäljningsdata. Ingen riktig kunddata visas.
          </p>
        </div>
      </main>
    </div>
  )
}
