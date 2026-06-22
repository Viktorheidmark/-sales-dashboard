/** Shared Recharts styling tokens for the dark intelligence workspace. */
export const CHART = {
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
} as const

export const chartTooltipStyle = {
  fontSize: 11,
  borderRadius: 8,
  border: `1px solid ${CHART.tooltipBorder}`,
  backgroundColor: CHART.tooltipBg,
  color: CHART.tooltipText,
}

export const chartAxisTick = { fontSize: 11, fill: CHART.axis }
export const chartAxisTickSm = { fontSize: 10, fill: CHART.axis }
