/**
 * Central tenant branding configuration.
 * Add one entry per supplier. Components must consume via CSS vars or
 * useTenantBranding() hook — never hardcode tenant colors in leaf components.
 */

export interface TenantBranding {
  monogram: string
  primary: string
  primaryHover: string
  /** Translucent soft tint, e.g. rgba(R,G,B,0.10) */
  soft: string
  /** Light muted variant for secondary chart elements */
  muted: string
  /** Very translucent glow, e.g. rgba(R,G,B,0.18) */
  glow: string
  chartPrimary: string
  chartMuted: string
}

// Default Solvigo blue — used when no tenant matches or on logout
export const SOLVIGO_DEFAULT: TenantBranding = {
  monogram: 'S',
  primary: '#3B82F6',
  primaryHover: '#2563EB',
  soft: 'rgba(59,130,246,0.10)',
  muted: '#93C5FD',
  glow: 'rgba(59,130,246,0.18)',
  chartPrimary: '#3B82F6',
  chartMuted: '#93C5FD',
}

const TENANT_CONFIGS: Array<{
  match: (name: string) => boolean
  branding: TenantBranding
}> = [
  {
    // Coca-Cola Europacific Partners Sverige
    match: name => /coca.?cola/i.test(name),
    branding: {
      monogram: 'C',
      primary: '#C62828',
      primaryHover: '#A91D1D',
      soft: 'rgba(198,40,40,0.10)',
      muted: '#F2B8B5',
      glow: 'rgba(198,40,40,0.18)',
      chartPrimary: '#C62828',
      chartMuted: '#F2B8B5',
    },
  },
  {
    // PepsiCo Northern Europe
    match: name => /pepsi/i.test(name),
    branding: {
      monogram: 'P',
      primary: '#1463D8',
      primaryHover: '#0F4FAF',
      soft: 'rgba(20,99,216,0.10)',
      muted: '#A9C8FF',
      glow: 'rgba(20,99,216,0.18)',
      chartPrimary: '#1463D8',
      chartMuted: '#A9C8FF',
    },
  },
  {
    // Orkla Snacks Sverige
    match: name => /orkla/i.test(name),
    branding: {
      monogram: 'O',
      primary: '#E56A25',
      primaryHover: '#C95316',
      soft: 'rgba(229,106,37,0.10)',
      muted: '#F6C3A5',
      glow: 'rgba(229,106,37,0.18)',
      chartPrimary: '#E56A25',
      chartMuted: '#F6C3A5',
    },
  },
  {
    // Estrella AB
    match: name => /estrella/i.test(name),
    branding: {
      monogram: 'E',
      primary: '#6C3CCB',
      primaryHover: '#542BA5',
      soft: 'rgba(108,60,203,0.10)',
      muted: '#D1B8F6',
      glow: 'rgba(108,60,203,0.18)',
      chartPrimary: '#6C3CCB',
      chartMuted: '#D1B8F6',
    },
  },
]

export function getTenantBranding(supplierName: string): TenantBranding {
  const found = TENANT_CONFIGS.find(t => t.match(supplierName))
  return found ? found.branding : SOLVIGO_DEFAULT
}

const CSS_VAR_MAP: Array<[string, keyof TenantBranding]> = [
  ['--tenant-primary',       'primary'],
  ['--tenant-primary-hover', 'primaryHover'],
  ['--tenant-soft',          'soft'],
  ['--tenant-muted',         'muted'],
  ['--tenant-glow',          'glow'],
  ['--tenant-chart-primary', 'chartPrimary'],
  ['--tenant-chart-muted',   'chartMuted'],
]

/** Inject tenant CSS custom properties onto the document root. */
export function applyTenantTheme(branding: TenantBranding): void {
  const style = document.documentElement.style
  for (const [cssVar, key] of CSS_VAR_MAP) {
    style.setProperty(cssVar, String(branding[key]))
  }
}

/** Reset to Solvigo default on logout. */
export function resetTenantTheme(): void {
  applyTenantTheme(SOLVIGO_DEFAULT)
}

/** Static map for login-page demo rows (user not yet authenticated). */
export const DEMO_ROW_COLORS: Record<string, string> = {
  'cocacola@demo.solvigo':  '#C62828',
  'pepsico@demo.solvigo':   '#1463D8',
  'olw@demo.solvigo':       '#E56A25',
  'estrella@demo.solvigo':  '#6C3CCB',
}
