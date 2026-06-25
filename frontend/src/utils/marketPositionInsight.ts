import type { MarketShareResponse } from '../api/types'

const STABLE_SHARE_DELTA_PP = 0.5

function formatShareDeltaPp(delta: number): string {
  const sign = delta > 0 ? '+' : ''
  return `${sign}${delta.toLocaleString('sv-SE', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}`
}

export function buildMarketPositionInsight(data: MarketShareResponse): string {
  const prev = data.prev_market_share_pct

  if (
    prev != null
    && data.category_total_revenue > 0
    && data.prev_date_range != null
  ) {
    const delta = data.market_share_pct - prev

    if (Math.abs(delta) < STABLE_SHARE_DELTA_PP) {
      return 'Andelen är stabil jämfört med föregående period.'
    }

    return `Din andel är ${formatShareDeltaPp(delta)} procentenheter mot föregående period.`
  }

  return 'Marknadsandel baserad på tillgänglig kategoridata.'
}

export function formatSupplierRankLine(
  rank: number | null,
  total: number | null,
): string | null {
  if (rank == null || total == null || total < 2 || rank < 1 || rank > total) {
    return null
  }
  return `#${rank} av ${total} leverantörer i kategorin`
}
