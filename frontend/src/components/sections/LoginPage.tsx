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
    <>
      <style>{`
        @keyframes glowDrift1 {
          0%, 100% { transform: translate(0, 0) scale(1); }
          50% { transform: translate(4%, -6%) scale(1.08); }
        }
        @keyframes glowDrift2 {
          0%, 100% { transform: translate(0, 0) scale(1); }
          50% { transform: translate(-5%, 4%) scale(1.1); }
        }
        @keyframes glowDrift3 {
          0%, 100% { transform: translate(0, 0) scale(1); }
          50% { transform: translate(3%, 5%) scale(0.95); }
        }
        @keyframes ambientFloat1 {
          0%, 100% { transform: translateY(0) rotate(-1deg); }
          50% { transform: translateY(-12px) rotate(1deg); }
        }
        @keyframes ambientFloat2 {
          0%, 100% { transform: translateY(0) rotate(1deg); }
          50% { transform: translateY(-16px) rotate(-0.5deg); }
        }
        @keyframes ambientFloat3 {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-10px); }
        }
        @keyframes ambientFloat4 {
          0%, 100% { transform: translateY(0) rotate(0.5deg); }
          50% { transform: translateY(-8px) rotate(-1deg); }
        }
        @keyframes nodePulse {
          0%, 100% { opacity: 0.4; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.12); }
        }
        @keyframes chartDraw {
          from { stroke-dashoffset: 280; }
          to { stroke-dashoffset: 0; }
        }
        @keyframes loginFadeIn {
          from { opacity: 0; transform: translateY(18px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes cardFadeIn {
          from { opacity: 0; transform: translateY(24px) scale(0.98); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }

        .login-page {
          position: relative;
          min-height: 100vh;
          font-family: 'Inter', system-ui, sans-serif;
          overflow-x: hidden;
          /* Light theme (default — matches ThemeProvider DEFAULT_THEME) */
          --login-bg-gradient: linear-gradient(160deg, #f4f7fc 0%, #e8eef8 48%, #f8fafc 100%);
          --login-glow-1: rgba(59, 130, 246, 0.14);
          --login-glow-2: rgba(139, 92, 246, 0.12);
          --login-glow-3: rgba(56, 189, 248, 0.1);
          --login-grid-line: rgba(59, 130, 246, 0.07);
          --login-card-bg: rgba(255, 255, 255, 0.88);
          --login-card-border: rgba(148, 163, 184, 0.22);
          --login-card-shadow: 0 24px 80px rgba(15, 23, 42, 0.08), 0 0 0 1px rgba(59, 130, 246, 0.05) inset, 0 0 72px rgba(59, 130, 246, 0.07);
          --login-text-primary: #0f172a;
          --login-text-secondary: #475569;
          --login-text-muted: #64748b;
          --login-text-faint: #94a3b8;
          --login-eyebrow: #64748b;
          --login-input-bg: rgba(255, 255, 255, 0.92);
          --login-input-border: rgba(148, 163, 184, 0.35);
          --login-input-color: #0f172a;
          --login-input-placeholder: #94a3b8;
          --login-input-focus-bg: #fff;
          --login-divider: rgba(148, 163, 184, 0.25);
          --login-demo-bg: rgba(255, 255, 255, 0.65);
          --login-demo-border: rgba(148, 163, 184, 0.28);
          --login-demo-hover-bg: rgba(59, 130, 246, 0.06);
          --login-demo-selected-bg: rgba(59, 130, 246, 0.1);
          --login-demo-selected-border: rgba(59, 130, 246, 0.35);
          --login-ambient-bg: rgba(255, 255, 255, 0.78);
          --login-ambient-border: rgba(148, 163, 184, 0.28);
          --login-ambient-shadow: 0 10px 36px rgba(15, 23, 42, 0.07), 0 0 28px rgba(59, 130, 246, 0.05);
          --login-ambient-label: #94a3b8;
          --login-ambient-tag: #64748b;
          --login-logo-bg: rgba(59, 130, 246, 0.1);
          --login-logo-border: rgba(59, 130, 246, 0.22);
          --login-logo-glow: 0 0 24px rgba(59, 130, 246, 0.12);
          --login-logo-icon: #2563eb;
          --login-demo-avatar-bg: rgba(59, 130, 246, 0.12);
          --login-demo-avatar-color: #2563eb;
          --login-error-text: #b91c1c;
          --login-error-bg: rgba(254, 226, 226, 0.85);
          --login-error-border: rgba(248, 113, 113, 0.35);
          --login-chart-fill: rgba(59, 130, 246, 0.18);
          --login-chart-stroke: rgba(37, 99, 235, 0.7);
          --login-node-stroke: rgba(139, 92, 246, 0.35);
          --login-node-fill: rgba(124, 58, 237, 0.75);
          --login-bar-fill-top: rgba(59, 130, 246, 0.45);
          --login-bar-fill-bottom: rgba(59, 130, 246, 0.12);
        }

        html.dark .login-page {
          --login-bg-gradient: linear-gradient(160deg, #050B18 0%, #0A1224 45%, #050B18 100%);
          --login-glow-1: rgba(59, 130, 246, 0.22);
          --login-glow-2: rgba(99, 102, 241, 0.2);
          --login-glow-3: rgba(34, 211, 238, 0.14);
          --login-grid-line: rgba(255, 255, 255, 0.025);
          --login-card-bg: rgba(10, 15, 30, 0.72);
          --login-card-border: rgba(255, 255, 255, 0.08);
          --login-card-shadow: 0 24px 80px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba(59, 130, 246, 0.06) inset, 0 0 60px rgba(59, 130, 246, 0.08);
          --login-text-primary: #fff;
          --login-text-secondary: rgba(255, 255, 255, 0.55);
          --login-text-muted: rgba(255, 255, 255, 0.4);
          --login-text-faint: rgba(255, 255, 255, 0.32);
          --login-eyebrow: rgba(148, 163, 184, 0.75);
          --login-input-bg: rgba(255, 255, 255, 0.04);
          --login-input-border: rgba(255, 255, 255, 0.08);
          --login-input-color: #fff;
          --login-input-placeholder: rgba(255, 255, 255, 0.35);
          --login-input-focus-bg: rgba(255, 255, 255, 0.06);
          --login-divider: rgba(255, 255, 255, 0.08);
          --login-demo-bg: rgba(255, 255, 255, 0.03);
          --login-demo-border: rgba(255, 255, 255, 0.08);
          --login-demo-hover-bg: rgba(59, 130, 246, 0.08);
          --login-demo-selected-bg: rgba(59, 130, 246, 0.12);
          --login-demo-selected-border: rgba(96, 165, 250, 0.45);
          --login-ambient-bg: rgba(255, 255, 255, 0.05);
          --login-ambient-border: rgba(255, 255, 255, 0.09);
          --login-ambient-shadow: 0 8px 32px rgba(0, 0, 0, 0.25), 0 0 24px rgba(59, 130, 246, 0.06);
          --login-ambient-label: rgba(255, 255, 255, 0.38);
          --login-ambient-tag: rgba(255, 255, 255, 0.45);
          --login-logo-bg: rgba(59, 130, 246, 0.14);
          --login-logo-border: rgba(59, 130, 246, 0.28);
          --login-logo-glow: 0 0 24px rgba(59, 130, 246, 0.15);
          --login-logo-icon: #60a5fa;
          --login-demo-avatar-bg: rgba(59, 130, 246, 0.15);
          --login-demo-avatar-color: #60a5fa;
          --login-error-text: #fca5a5;
          --login-error-bg: rgba(220, 38, 38, 0.12);
          --login-error-border: rgba(248, 113, 113, 0.25);
          --login-chart-fill: rgba(59, 130, 246, 0.3);
          --login-chart-stroke: rgba(96, 165, 250, 0.8);
          --login-node-stroke: rgba(139, 92, 246, 0.4);
          --login-node-fill: rgba(167, 139, 250, 0.85);
          --login-bar-fill-top: rgba(96, 165, 250, 0.5);
          --login-bar-fill-bottom: rgba(59, 130, 246, 0.12);
        }

        .login-eyebrow { color: var(--login-eyebrow); }
        .login-text-primary { color: var(--login-text-primary); }
        .login-text-secondary { color: var(--login-text-secondary); }
        .login-text-muted { color: var(--login-text-muted); }
        .login-text-faint { color: var(--login-text-faint); }
        .login-label { color: var(--login-text-secondary); }
        .login-divider { background: var(--login-divider); }
        .login-logo-box {
          background: var(--login-logo-bg);
          border: 1px solid var(--login-logo-border);
          box-shadow: var(--login-logo-glow);
        }
        .login-logo-icon { color: var(--login-logo-icon); }
        .login-error {
          color: var(--login-error-text);
          background: var(--login-error-bg);
          border: 1px solid var(--login-error-border);
        }
        .login-demo-name { color: var(--login-text-primary); }
        .login-demo-email { color: var(--login-text-faint); }
        .login-demo-badge { color: var(--login-logo-icon); }
        .login-demo-avatar {
          background: var(--login-demo-avatar-bg);
          color: var(--login-demo-avatar-color);
        }
        .login-demo-avatar.selected {
          background: linear-gradient(135deg, #2563EB, #3B82F6);
          color: white;
        }

        .login-bg-layer {
          position: absolute;
          inset: 0;
          background: var(--login-bg-gradient);
        }
        .login-glow-orb-1 {
          background: radial-gradient(circle, var(--login-glow-1) 0%, transparent 68%);
        }
        .login-glow-orb-2 {
          background: radial-gradient(circle, var(--login-glow-2) 0%, transparent 70%);
        }
        .login-glow-orb-3 {
          background: radial-gradient(circle, var(--login-glow-3) 0%, transparent 72%);
        }
        .login-grid-overlay {
          background-image:
            linear-gradient(var(--login-grid-line) 1px, transparent 1px),
            linear-gradient(90deg, var(--login-grid-line) 1px, transparent 1px);
        }
        .login-ambient-card {
          background: var(--login-ambient-bg);
          backdrop-filter: blur(14px);
          -webkit-backdrop-filter: blur(14px);
          border: 1px solid var(--login-ambient-border);
          border-radius: 14px;
          box-shadow: var(--login-ambient-shadow);
        }
        .login-ambient-label {
          color: var(--login-ambient-label);
        }
        .login-ambient-tag {
          color: var(--login-ambient-tag);
        }

        .login-glass-card {
          animation: cardFadeIn 0.65s ease-out 0.1s both;
          width: 100%;
          max-width: 500px;
          padding: 36px 40px 32px;
          border-radius: 20px;
          background: var(--login-card-bg);
          backdrop-filter: blur(18px);
          -webkit-backdrop-filter: blur(18px);
          border: 1px solid var(--login-card-border);
          box-shadow: var(--login-card-shadow);
        }

        .login-input {
          width: 100%;
          height: 48px;
          border-radius: 10px;
          border: 1px solid var(--login-input-border);
          background: var(--login-input-bg);
          font-size: 15px;
          padding: 0 16px;
          color: var(--login-input-color);
          outline: none;
          transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
          box-sizing: border-box;
        }
        .login-input:focus {
          border-color: #3B82F6;
          box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.14);
          background: var(--login-input-focus-bg);
        }
        .login-input::placeholder { color: var(--login-input-placeholder); }
        .login-input:disabled { opacity: 0.45; cursor: not-allowed; }

        .login-btn {
          width: 100%;
          height: 48px;
          border-radius: 10px;
          background: linear-gradient(135deg, #2563EB 0%, #3B82F6 100%);
          color: white;
          font-size: 15px;
          font-weight: 600;
          border: none;
          cursor: pointer;
          margin-top: 10px;
          transition: transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
        }
        .login-btn:hover:not(:disabled) {
          transform: translateY(-1px);
          box-shadow: 0 8px 28px rgba(37, 99, 235, 0.45);
          filter: brightness(1.05);
        }
        .login-btn:disabled {
          opacity: 0.4;
          cursor: not-allowed;
          transform: none;
          box-shadow: none;
        }

        .demo-btn {
          width: 100%;
          padding: 12px 16px;
          border-radius: 10px;
          background: var(--login-demo-bg);
          border: 1px solid var(--login-demo-border);
          display: flex;
          align-items: center;
          gap: 12px;
          cursor: pointer;
          margin-bottom: 8px;
          transition: all 0.15s ease;
          text-align: left;
        }
        .demo-btn:hover:not(:disabled) {
          background: var(--login-demo-hover-bg);
          border-color: rgba(59, 130, 246, 0.35);
          box-shadow: 0 0 20px rgba(59, 130, 246, 0.12);
          transform: translateX(2px);
        }
        .demo-btn.selected {
          background: var(--login-demo-selected-bg);
          border-color: var(--login-demo-selected-border);
          box-shadow: 0 0 24px rgba(59, 130, 246, 0.15);
        }
        .demo-btn:disabled { opacity: 0.4; cursor: not-allowed; }

        .login-el-1 { animation: loginFadeIn 0.5s ease-out 0.15s both; }
        .login-el-2 { animation: loginFadeIn 0.5s ease-out 0.25s both; }
        .login-el-3 { animation: loginFadeIn 0.5s ease-out 0.35s both; }
        .login-el-4 { animation: loginFadeIn 0.5s ease-out 0.45s both; }
        .login-el-5 { animation: loginFadeIn 0.5s ease-out 0.55s both; }

        .login-float { position: absolute; pointer-events: none; z-index: 1; }
        .login-float-1 { top: 8%; left: 6%; animation: ambientFloat1 9s ease-in-out infinite; }
        .login-float-2 { top: 14%; right: 8%; animation: ambientFloat2 11s ease-in-out infinite; animation-delay: -2s; }
        .login-float-3 { top: 42%; left: 4%; animation: ambientFloat3 10s ease-in-out infinite; animation-delay: -1s; }
        .login-float-4 { top: 38%; right: 5%; animation: ambientFloat4 8s ease-in-out infinite; animation-delay: -3s; }
        .login-float-5 { bottom: 14%; left: 10%; animation: ambientFloat2 12s ease-in-out infinite; animation-delay: -4s; }
        .login-float-6 { bottom: 18%; right: 9%; animation: ambientFloat1 10s ease-in-out infinite; animation-delay: -2.5s; }

        @media (max-width: 900px) {
          .login-float-3, .login-float-4 { display: none; }
          .login-float-1, .login-float-2 { transform: scale(0.85); opacity: 0.7; }
          .login-float-5, .login-float-6 { transform: scale(0.8); opacity: 0.65; }
        }

        @media (max-width: 640px) {
          .login-glass-card { padding: 28px 24px 24px; max-width: none; }
          .login-float-5, .login-float-6 { display: none; }
          .login-float-1 { top: 4%; left: 2%; transform: scale(0.7); opacity: 0.5; }
          .login-float-2 { top: 6%; right: 2%; transform: scale(0.7); opacity: 0.5; }
        }

        @media (prefers-reduced-motion: reduce) {
          .login-el-1, .login-el-2, .login-el-3, .login-el-4, .login-el-5,
          .login-glass-card, .login-glow-orb, .login-float,
          .login-node-pulse { animation: none !important; }
          .login-chart-line { stroke-dashoffset: 0 !important; }
        }
      `}</style>

      <div className="login-page">
        <PremiumBackground />

        <div style={{ position: 'fixed', top: 20, right: 20, zIndex: 20 }}>
          <ThemeToggle compact />
        </div>

        <main
          style={{
            position: 'relative',
            zIndex: 10,
            minHeight: '100vh',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '48px 20px 56px',
          }}
        >
          <p
            className="login-el-1 login-eyebrow"
            style={{
              margin: '0 0 20px',
              fontSize: 12,
              fontWeight: 500,
              letterSpacing: '0.14em',
              textTransform: 'uppercase',
            }}
          >
            AI-driven leverantörsanalys
          </p>

          <div className="login-glass-card">
            <div className="login-el-1" style={{ marginBottom: 32 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 28 }}>
                <div className="login-logo-box" style={{
                  width: 48,
                  height: 48,
                  borderRadius: 12,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}>
                  <span className="login-logo-icon" style={{ fontSize: 22, fontWeight: 700, lineHeight: 1 }}>◈</span>
                </div>
                <div>
                  <p className="login-text-muted" style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.2em', textTransform: 'uppercase', lineHeight: 1, margin: 0 }}>
                    Solvigo
                  </p>
                  <p className="login-text-primary" style={{ fontSize: 16, fontWeight: 600, lineHeight: 1.2, marginTop: 4, marginBottom: 0 }}>
                    Sales Intelligence
                  </p>
                </div>
              </div>
              <h1 className="login-text-primary" style={{ fontSize: 28, fontWeight: 600, margin: 0, lineHeight: 1.2 }}>
                Välkommen tillbaka
              </h1>
              <p className="login-text-secondary" style={{ fontSize: 15, marginTop: 10, marginBottom: 0, lineHeight: 1.5 }}>
                Logga in på ditt konto
              </p>
              <p className="login-text-faint" style={{ fontSize: 13, marginTop: 8, marginBottom: 0, lineHeight: 1.45 }}>
                Förstå vad som driver försäljningen
              </p>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="login-el-2" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                <div>
                  <label htmlFor="login-email" className="login-label" style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 8 }}>
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
                    className="login-input"
                  />
                </div>

                <div>
                  <label htmlFor="login-password" className="login-label" style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 8 }}>
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
                    className="login-input"
                  />
                </div>
              </div>

              {error && (
                <p
                  role="alert"
                  className="login-error"
                  style={{
                    fontSize: 13,
                    borderRadius: 10,
                    padding: '12px 14px',
                    marginTop: 16,
                    lineHeight: 1.4,
                  }}
                >
                  {error}
                </p>
              )}

              <div className="login-el-3">
                <button
                  type="submit"
                  disabled={loading || !email.trim() || !password}
                  className="login-btn"
                >
                  {loading && (
                    <span style={{
                      width: 16,
                      height: 16,
                      border: '2px solid rgba(255,255,255,0.4)',
                      borderTopColor: 'white',
                      borderRadius: '50%',
                      animation: 'spin 0.7s linear infinite',
                      display: 'inline-block',
                    }} />
                  )}
                  {loading ? 'Loggar in…' : 'Logga in'}
                </button>
              </div>
            </form>

            <div className="login-el-4">
              <div className="login-divider" style={{ height: 1, margin: '32px 0 20px' }} />
              <p className="login-text-muted" style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 14 }}>
                Demoarbetsytor
              </p>

              <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
                {DEMO_ACCOUNTS.map(account => {
                  const selected = email === account.email
                  return (
                    <li key={account.email}>
                      <button
                        type="button"
                        onClick={() => fillDemo(account.email)}
                        disabled={loading}
                        className={`demo-btn${selected ? ' selected' : ''}`}
                      >
                        <span className={`login-demo-avatar${selected ? ' selected' : ''}`} style={{
                          width: 32,
                          height: 32,
                          borderRadius: '50%',
                          fontSize: 13,
                          fontWeight: 600,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                          transition: 'all 0.15s ease',
                        }}>
                          {account.label.charAt(0)}
                        </span>
                        <span style={{ minWidth: 0, flex: 1 }}>
                          <span className="login-demo-name" style={{ display: 'block', fontSize: 14, fontWeight: 500, lineHeight: 1.3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {account.label}
                          </span>
                          <span className="login-demo-email" style={{ display: 'block', fontSize: 11, fontFamily: 'ui-monospace, monospace', marginTop: 2 }}>
                            {account.email}
                          </span>
                        </span>
                        {selected && (
                          <span className="login-demo-badge" style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', flexShrink: 0 }}>
                            Vald
                          </span>
                        )}
                      </button>
                    </li>
                  )
                })}
              </ul>

              <p className="login-text-faint" style={{ fontSize: 11, marginTop: 12 }}>
                Demolösenord:{' '}
                <span className="login-text-secondary" style={{ fontFamily: 'ui-monospace, monospace' }}>{DEMO_PASSWORD}</span>
              </p>
            </div>

            <p className="login-el-5 login-text-faint" style={{ fontSize: 11, textAlign: 'center', marginTop: 24, marginBottom: 0, lineHeight: 1.5 }}>
              Demo med syntetisk försäljningsdata.
            </p>
          </div>
        </main>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </>
  )
}

// ─── Full-page premium background + ambient floats ───────────────────────────

function PremiumBackground() {
  return (
    <div style={{ position: 'fixed', inset: 0, overflow: 'hidden', pointerEvents: 'none' }}>
      <div className="login-bg-layer" />

      <div
        className="login-glow-orb login-glow-orb-1"
        style={{
          position: 'absolute',
          top: '-10%',
          left: '-5%',
          width: '55vw',
          height: '55vw',
          maxWidth: 700,
          maxHeight: 700,
          filter: 'blur(70px)',
          animation: 'glowDrift1 14s ease-in-out infinite',
        }}
      />
      <div
        className="login-glow-orb login-glow-orb-2"
        style={{
          position: 'absolute',
          top: '20%',
          right: '-8%',
          width: '45vw',
          height: '45vw',
          maxWidth: 560,
          maxHeight: 560,
          filter: 'blur(60px)',
          animation: 'glowDrift2 16s ease-in-out infinite',
        }}
      />
      <div
        className="login-glow-orb login-glow-orb-3"
        style={{
          position: 'absolute',
          bottom: '-5%',
          left: '25%',
          width: '40vw',
          height: '40vw',
          maxWidth: 480,
          maxHeight: 480,
          filter: 'blur(55px)',
          animation: 'glowDrift3 12s ease-in-out infinite',
        }}
      />

      <div className="login-grid-overlay" style={{
        position: 'absolute',
        inset: 0,
        backgroundSize: '48px 48px',
        maskImage: 'radial-gradient(ellipse 80% 70% at 50% 50%, black 20%, transparent 100%)',
        WebkitMaskImage: 'radial-gradient(ellipse 80% 70% at 50% 50%, black 20%, transparent 100%)',
      }} />

      <div className="login-float login-float-1">
        <AmbientTrendCard />
      </div>
      <div className="login-float login-float-2">
        <AmbientNodeCard />
      </div>
      <div className="login-float login-float-3">
        <AmbientTagCard label="Insight" tag="Analysis" />
      </div>
      <div className="login-float login-float-4">
        <AmbientTagCard label="Forecast" tag="Pattern" wide />
      </div>
      <div className="login-float login-float-5">
        <AmbientMiniChart />
      </div>
      <div className="login-float login-float-6">
        <AmbientTagCard label="Signal" tag="Trend" small />
      </div>
    </div>
  )
}

function ambientGlass(extra?: React.CSSProperties): React.CSSProperties {
  return extra ?? {}
}

function AmbientTrendCard() {
  return (
    <div className="login-ambient-card" style={ambientGlass({ width: 220, padding: '14px 16px 12px' })}>
      <p className="login-ambient-label" style={{ fontSize: 9, fontWeight: 600, letterSpacing: '0.14em', textTransform: 'uppercase', margin: '0 0 10px' }}>
        Trend
      </p>
      <svg viewBox="0 0 180 52" width="100%" height={52} aria-hidden>
        <defs>
          <linearGradient id="ambientChartGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--login-chart-fill)" />
            <stop offset="100%" stopColor="transparent" />
          </linearGradient>
        </defs>
        <path d="M0 40 L30 36 L60 38 L90 24 L120 28 L150 16 L180 10 L180 52 L0 52 Z" fill="url(#ambientChartGrad)" />
        <polyline
          className="login-chart-line"
          points="0,40 30,36 60,38 90,24 120,28 150,16 180,10"
          fill="none"
          stroke="var(--login-chart-stroke)"
          strokeWidth="1.75"
          strokeLinecap="round"
          strokeDasharray="280"
          style={{ animation: 'chartDraw 2s ease-out 0.3s both' }}
        />
      </svg>
    </div>
  )
}

function AmbientNodeCard() {
  const nodes = [{ cx: 24, cy: 44 }, { cx: 68, cy: 24 }, { cx: 112, cy: 38 }, { cx: 156, cy: 18 }]
  return (
    <div className="login-ambient-card" style={ambientGlass({ width: 200, padding: '14px 16px' })}>
      <p className="login-ambient-label" style={{ fontSize: 9, fontWeight: 600, letterSpacing: '0.14em', textTransform: 'uppercase', margin: '0 0 10px' }}>
        Signal
      </p>
      <svg viewBox="0 0 180 56" width="100%" height={56} aria-hidden>
        {nodes.slice(0, -1).map((n, i) => (
          <line key={i} x1={n.cx} y1={n.cy} x2={nodes[i + 1].cx} y2={nodes[i + 1].cy} stroke="var(--login-node-stroke)" strokeWidth="1.25" />
        ))}
        {nodes.map((n, i) => (
          <circle
            key={i}
            className="login-node-pulse"
            cx={n.cx}
            cy={n.cy}
            r={5}
            fill="var(--login-node-fill)"
            style={{ animation: `nodePulse 3.5s ease-in-out ${i * 0.4}s infinite` }}
          />
        ))}
      </svg>
    </div>
  )
}

function AmbientTagCard({
  label,
  tag,
  small = false,
  wide = false,
}: {
  label: string
  tag: string
  small?: boolean
  wide?: boolean
}) {
  return (
    <div className="login-ambient-card" style={ambientGlass({
      width: small ? 130 : wide ? 175 : 150,
      padding: small ? '10px 12px' : '12px 14px',
    })}>
      <p className="login-ambient-label" style={{ fontSize: 9, fontWeight: 600, letterSpacing: '0.14em', textTransform: 'uppercase', margin: 0 }}>
        {label}
      </p>
      <div style={{
        marginTop: 8,
        height: 3,
        borderRadius: 2,
        background: 'linear-gradient(90deg, rgba(59,130,246,0.55), rgba(139,92,246,0.25), transparent)',
      }} />
      <p className="login-ambient-tag" style={{ fontSize: small ? 10 : 11, margin: '8px 0 0', fontWeight: 500 }}>
        {tag}
      </p>
    </div>
  )
}

function AmbientMiniChart() {
  return (
    <div className="login-ambient-card" style={ambientGlass({ width: 160, padding: '12px 14px' })}>
      <p className="login-ambient-label" style={{ fontSize: 9, fontWeight: 600, letterSpacing: '0.14em', textTransform: 'uppercase', margin: '0 0 8px' }}>
        Analysis
      </p>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 5, height: 36 }}>
        {[0.45, 0.7, 0.55, 0.85, 0.6, 0.75].map((h, i) => (
          <div
            key={i}
            style={{
              flex: 1,
              height: `${h * 100}%`,
              borderRadius: 3,
              background: `linear-gradient(180deg, var(--login-bar-fill-top) 0%, var(--login-bar-fill-bottom) 100%)`,
              opacity: 0.55 + i * 0.08,
            }}
          />
        ))}
      </div>
    </div>
  )
}
