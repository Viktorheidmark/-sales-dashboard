import { useTheme } from '../../theme/ThemeProvider'

interface ThemeToggleProps {
  compact?: boolean
  className?: string
}

export function ThemeToggle({ compact = false, className = '' }: ThemeToggleProps) {
  const { theme, setTheme } = useTheme()
  const isDark = theme === 'dark'

  if (compact) {
    return (
      <button
        type="button"
        onClick={() => setTheme(isDark ? 'light' : 'dark')}
        className={`inline-flex items-center justify-center w-8 h-8 rounded-lg border border-workspace-border bg-workspace-elevated text-theme-muted hover:text-theme-strong hover:bg-[var(--surface-hover)] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50 ${className}`}
        aria-label={isDark ? 'Byt till ljust tema' : 'Byt till mörkt tema'}
        title={isDark ? 'Ljust tema' : 'Mörkt tema'}
      >
        {isDark ? (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24" aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
          </svg>
        ) : (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24" aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
          </svg>
        )}
      </button>
    )
  }

  return (
    <div
      className={`segment-control w-full ${className}`}
      role="group"
      aria-label="Tema"
    >
      <button
        type="button"
        onClick={() => setTheme('dark')}
        aria-pressed={isDark}
        className={`segment-btn flex-1 justify-center ${isDark ? 'segment-btn-active' : ''}`}
      >
        Mörkt
      </button>
      <button
        type="button"
        onClick={() => setTheme('light')}
        aria-pressed={!isDark}
        className={`segment-btn flex-1 justify-center ${!isDark ? 'segment-btn-active' : ''}`}
      >
        Ljust
      </button>
    </div>
  )
}
