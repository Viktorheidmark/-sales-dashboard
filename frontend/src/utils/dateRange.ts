import { daysAgo, today } from './format'

export type DatePreset = '30d' | '90d' | '180d' | 'all'

export const DATE_PRESETS: { value: DatePreset; label: string }[] = [
  { value: '30d',  label: '30 dagar' },
  { value: '90d',  label: '90 dagar' },
  { value: '180d', label: '180 dagar' },
  { value: 'all',  label: 'All tid' },
]

export function presetToDates(preset: DatePreset): {
  startDate: string | undefined
  endDate: string | undefined
  granularity: string
  days: number
} {
  const end = today()
  switch (preset) {
    case '30d':  return { startDate: daysAgo(30),  endDate: end, granularity: 'day',   days: 30 }
    case '90d':  return { startDate: daysAgo(90),  endDate: end, granularity: 'week',  days: 90 }
    case '180d': return { startDate: daysAgo(180), endDate: end, granularity: 'month', days: 180 }
    case 'all':  return { startDate: undefined,    endDate: undefined, granularity: 'month', days: 180 }
  }
}

export function defaultCategory(supplierName: string): string {
  const name = supplierName.toLowerCase()
  if (name.includes('coca-cola') || name.includes('cocacola') || name.includes('pepsi')) return 'Läsk'
  if (name.includes('orkla') || name.includes('snacks') || name.includes('estrella') || name.includes('olw')) return 'Chips & snacks'
  return 'Läsk'
}

/** Display label for the active overview period (products/regions cards). */
export function overviewPeriodContextLabel(preset: DatePreset): string {
  switch (preset) {
    case '30d':
      return 'Senaste 30 dagarna'
    case '90d':
      return 'Senaste 90 dagarna'
    case '180d':
      return 'Senaste 180 dagarna'
    case 'all':
      return 'Hela tillgängliga perioden'
  }
}
