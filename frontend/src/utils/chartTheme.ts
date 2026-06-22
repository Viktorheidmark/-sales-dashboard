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
  line: '#4d7cff',
  barPrimary: '#4d7cff',
  barSecondary: '#334155',
  referenceLine: '#475569',
  tooltipBg: '#1c2531',
  tooltipBorder: '#2a3544',
  tooltipText: '#e2e8f0',
  tooltipMuted: '#94a3b8',
  pieColors: ['#4d7cff', '#334155', '#475569', '#64748b'],
  pieMuted: '#1e293b',
}

const CHART_LIGHT: ChartTokens = {
  grid: '#e2e8f0',
  axis: '#64748b',
  line: '#3d66e0',
  barPrimary: '#4d7cff',
  barSecondary: '#cbd5e1',
  referenceLine: '#94a3b8',
  tooltipBg: '#ffffff',
  tooltipBorder: '#e2e8f0',
  tooltipText: '#0f172a',
  tooltipMuted: '#64748b',
  pieColors: ['#4d7cff', '#94a3b8', '#cbd5e1', '#64748b'],
  pieMuted: '#e2e8f0',
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
