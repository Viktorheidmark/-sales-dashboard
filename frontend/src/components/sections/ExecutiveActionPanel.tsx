import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'
import type {
  DecliningProductItem,
  RegionItem,
  MarketShareResponse,
} from '../../api/types'
import { formatPct } from '../../utils/format'
import { Skeleton } from '../ui/Skeleton'

interface ExecutiveActionPanelProps {
  worst?: DecliningProductItem
  worstPct: string | null
  topRegion?: RegionItem
  marketShare: MarketShareResponse | null
  selectedCategory: string
  decliningLoading: boolean
  regionsLoading: boolean
  marketShareLoading: boolean
}

function PanelBlock({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <div className="py-4 border-b border-slate-200/70 last:border-0 last:pb-0 first:pt-0">
      <p className="text-xs font-medium text-slate-500 mb-2">{label}</p>
      {children}
    </div>
  )
}

export function ExecutiveActionPanel({
  worst,
  worstPct,
  topRegion,
  marketShare,
  selectedCategory,
  decliningLoading,
  regionsLoading,
  marketShareLoading,
}: ExecutiveActionPanelProps) {
  const anyLoading = decliningLoading || regionsLoading || marketShareLoading
  const hasContent = worst || topRegion || marketShare

  return (
    <aside className="rounded-xl border border-slate-200/80 bg-slate-50/60 flex flex-col h-full">
      <div className="px-5 pt-5 pb-1">
        <h2 className="text-sm font-semibold text-slate-800">Vad kräver åtgärd?</h2>
        <p className="text-xs text-slate-500 mt-1 leading-relaxed">
          Prioriterade signaler från vald period
        </p>
      </div>

      <div className="flex-1 px-5 py-4 flex flex-col">
        {anyLoading && !hasContent ? (
          <div className="space-y-4">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : (
          <div className="flex-1">
            {worst && worstPct && (
              <PanelBlock label="Produkt i nedgång">
                <p className="text-sm font-semibold text-slate-900 leading-snug">{worst.product_name}</p>
                <p className="mt-1.5 text-sm text-slate-600 leading-relaxed">
                  Omsättningen har fallit med {worstPct}% jämfört med föregående period.
                </p>
              </PanelBlock>
            )}

            {topRegion && (
              <PanelBlock label="Starkaste region">
                <p className="text-sm font-semibold text-slate-900">{topRegion.region}</p>
                <p className="mt-1.5 text-sm text-slate-600 leading-relaxed">
                  Genererar mest omsättning under perioden.
                </p>
              </PanelBlock>
            )}

            {marketShareLoading && !marketShare ? (
              <PanelBlock label="Marknadsandel">
                <Skeleton className="h-10 w-3/4" />
              </PanelBlock>
            ) : marketShare ? (
              <PanelBlock label="Marknadsandel">
                <p className="text-2xl font-bold text-slate-900 tabular-nums leading-none">
                  {formatPct(marketShare.market_share_pct)}
                </p>
                <p className="mt-1.5 text-sm text-slate-600 leading-relaxed">
                  Andel av {selectedCategory.toLowerCase()}kategorin.
                  {marketShare.competitor_count > 0 && (
                    <span className="text-slate-400">
                      {' '}Konkurrentdata visas enbart aggregerat ({marketShare.competitor_count} aktörer).
                    </span>
                  )}
                </p>
              </PanelBlock>
            ) : null}

            {!worst && !topRegion && !marketShare && !anyLoading && (
              <p className="text-sm text-slate-500 leading-relaxed py-2">
                Inga prioriterade signaler för vald period.
              </p>
            )}
          </div>
        )}

        <Link
          to="/assistant"
          className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-brand-600 hover:text-brand-700 transition-colors"
        >
          Öppna analysassistenten
          <span aria-hidden>→</span>
        </Link>
      </div>
    </aside>
  )
}
