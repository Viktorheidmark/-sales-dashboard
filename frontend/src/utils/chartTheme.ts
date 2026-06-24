import { useMemo } from 'react'
import { useTheme } from '../theme/ThemeProvider'

export type ChartTokens = {
  grid: string
  axis: string
  line: string
  barPrimary: string
  barSecondary: string
  referenceLine: string
  tooltipBg: string
  tooltipBorder: string
  tooltipText: string
  tooltipMuted: string
  pieColors: readonly string[]
  pieMuted: string
}

const CHART_DARK: ChartTokens = {
  grid: '#2a3544',
  axis: '#64748b',
  line: '#3B82F6',
  barPrimary: '#3B82F6',
  barSecondary: '#93C5FD',
  referenceLine: '#475569',
  tooltipBg: '#1c2531',
  tooltipBorder: '#2a3544',
  tooltipText: '#e2e8f0',
  tooltipMuted: '#94a3b8',
  pieColors: ['#3B82F6', '#94A3B8', '#64748b', '#475569'],
  pieMuted: '#E2E8F0',
}

const CHART_LIGHT: ChartTokens = {
  grid: '#e2e8f0',
  axis: '#64748b',
  line: '#3B82F6',
  barPrimary: '#3B82F6',
  barSecondary: '#93C5FD',
  referenceLine: '#94a3b8',
  tooltipBg: '#ffffff',
  tooltipBorder: '#e2e8f0',
  tooltipText: '#0f172a',
  tooltipMuted: '#64748b',
  pieColors: ['#3B82F6', '#94A3B8', '#CBD5E1', '#64748b'],
  pieMuted: '#E2E8F0',
}

export function getChartTokens(theme: 'dark' | 'light'): ChartTokens {
  return theme === 'dark' ? CHART_DARK : CHART_LIGHT
}

export function useChartTheme() {
  const { theme } = useTheme()

  return useMemo(() => {
    const chart = getChartTokens(theme)
    return {
      chart,
      chartTooltipStyle: {
        fontSize: 11,
        borderRadius: 8,
        border: `1px solid ${chart.tooltipBorder}`,
        backgroundColor: chart.tooltipBg,
        color: chart.tooltipText,
      },
      chartAxisTick: { fontSize: 11, fill: chart.axis },
      chartAxisTickSm: { fontSize: 10, fill: chart.axis },
    }
  }, [theme])
}
