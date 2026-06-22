import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import type { MarketShareResponse } from '../../api/types'
import { formatSEK, formatPct } from '../../utils/format'
import { Card, CardHeader, CardBody } from '../ui/Card'
import { Skeleton } from '../ui/Skeleton'
import { ErrorState } from '../ui/ErrorState'
import { MetaFooter } from '../ui/MetaFooter'

const CATEGORIES = ['Mejeri', 'Dryck', 'Mat och snacks']

interface MarketShareProps {
  data: MarketShareResponse | null
  loading: boolean
  error: string | null
  onRetry: () => void
  selectedCategory: string
  onCategoryChange: (c: string) => void
}

export function MarketShare({
  data, loading, error, onRetry,
  selectedCategory, onCategoryChange,
}: MarketShareProps) {
  const pieData = data
    ? [
        { name: 'Vår andel', value: data.supplier_revenue, color: '#4169e1' },
        { name: 'Konkurrenter (aggregat)', value: data.competitor_aggregate_revenue ?? 0, color: '#e2e8f0' },
      ]
    : []

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <h2 className="text-sm font-semibold text-zinc-700">Marknadsandel</h2>
          <select
            value={selectedCategory}
            onChange={e => onCategoryChange(e.target.value)}
            className="text-xs border border-zinc-200 rounded-md px-2 py-1 text-zinc-600 bg-white focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            {CATEGORIES.map(c => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
      </CardHeader>
      <CardBody>
        {loading ? (
          <div className="space-y-3">
            <div className="flex justify-center">
              <Skeleton className="w-40 h-40 rounded-full" />
            </div>
            <Skeleton className="h-4 w-1/2 mx-auto" />
          </div>
        ) : error || !data ? (
          <ErrorState message={error ?? 'Kunde inte hämta data.'} onRetry={onRetry} />
        ) : (
          <>
            <div className="flex items-center gap-6">
              {/* Donut chart */}
              <div className="shrink-0">
                <ResponsiveContainer width={160} height={160}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={48}
                      outerRadius={72}
                      dataKey="value"
                      startAngle={90}
                      endAngle={-270}
                      strokeWidth={0}
                    >
                      {pieData.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(v: number) => formatSEK(v)}
                      contentStyle={{ fontSize: 12, borderRadius: 8 }}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <p className="text-center -mt-2 text-2xl font-bold text-zinc-900 tabular-nums">
                  {formatPct(data.market_share_pct)}
                </p>
                <p className="text-center text-xs text-zinc-400 mt-0.5">er andel</p>
              </div>

              {/* Stats */}
              <div className="flex-1 space-y-3">
                <div>
                  <p className="text-xs text-zinc-400 uppercase tracking-wider">Vår omsättning</p>
                  <p className="text-lg font-bold text-zinc-900 tabular-nums">{formatSEK(data.supplier_revenue)}</p>
                </div>
                <div>
                  <p className="text-xs text-zinc-400 uppercase tracking-wider">Kategoritotal</p>
                  <p className="text-lg font-bold text-zinc-900 tabular-nums">{formatSEK(data.category_total_revenue)}</p>
                </div>
                <div className="rounded-lg bg-zinc-50 border border-zinc-100 px-3 py-2">
                  <p className="text-xs text-zinc-500 font-medium">
                    Konkurrenter ({data.competitor_count})
                    <span className="ml-1 text-zinc-400 font-normal">— enbart aggregat</span>
                  </p>
                  <p className="text-sm font-semibold text-zinc-700 tabular-nums mt-0.5">
                    {formatSEK(data.competitor_aggregate_revenue)}
                  </p>
                </div>
              </div>
            </div>
          </>
        )}
        {data && (
          <MetaFooter
            source={data.source}
            generatedAt={data.generated_at}
            limitations={data.limitations}
          />
        )}
      </CardBody>
    </Card>
  )
}
