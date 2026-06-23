/** Compact Swedish currency for Analysis Assistant charts and lists (values in SEK). */
export function formatCompactSEK(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'

  const sign = value < 0 ? '-' : ''
  const abs = Math.abs(value)

  if (abs < 1_000) {
    return `${sign}${Math.round(abs)} kr`
  }

  if (abs < 1_000_000) {
    const tkr = abs / 1_000
    const decimals = Math.abs(tkr - Math.round(tkr)) < 0.05 ? 0 : 1
    const formatted = tkr.toLocaleString('sv-SE', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })
    return `${sign}${formatted} tkr`
  }

  const mkr = abs / 1_000_000
  const decimals = Math.abs(mkr - Math.round(mkr)) < 0.05 ? 0 : 1
  const formatted = mkr.toLocaleString('sv-SE', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
  return `${sign}${formatted} mkr`
}
