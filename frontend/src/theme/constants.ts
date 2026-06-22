export const THEME_STORAGE_KEY = 'solvigo-theme'

export type Theme = 'dark' | 'light'

export const DEFAULT_THEME: Theme = 'dark'

export function isTheme(value: string | null): value is Theme {
  return value === 'dark' || value === 'light'
}

export function readStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    return stored === 'light' ? 'light' : DEFAULT_THEME
  } catch {
    return DEFAULT_THEME
  }
}

export function applyThemeToDocument(theme: Theme): void {
  document.documentElement.classList.toggle('dark', theme === 'dark')
  document.documentElement.style.colorScheme = theme
}
