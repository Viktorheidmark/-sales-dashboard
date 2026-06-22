import type { DecliningProductsResponse, RegionsResponse } from '../../api/types'

interface InsightStripProps {
  decliningData: DecliningProductsResponse | null
  regionsData: RegionsResponse | null
}

export function InsightStrip({ decliningData, regionsData }: InsightStripProps) {
  const worst = decliningData?.products[0]
  const topRegion = regionsData?.regions[0]

  if (!worst && !topRegion) return null

  const pct = worst?.revenue_change_pct != null
    ? Math.abs(worst.revenue_change_pct).toFixed(1)
    : null

  return (
    <div className="bg-white rounded-xl border border-zinc-200 shadow-sm px-5 py-4 flex items-start gap-3">
      <span className="w-2 h-2 rounded-full bg-amber-400 shrink-0 mt-1.5" />
      <div>
        <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1">Viktigaste insikten</p>
        <p className="text-sm text-zinc-800 leading-relaxed">
          {worst && pct && (
            <span>
              <span className="font-medium">{worst.product_name}</span> har fallit {pct}% jämfört med föregående period.{' '}
            </span>
          )}
          {topRegion && (
            <span>
              <span className="font-medium">{topRegion.region}</span> är vår starkaste region och driver mest omsättning.
            </span>
          )}
        </p>
      </div>
    </div>
  )
}
