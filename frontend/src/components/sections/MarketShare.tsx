import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import type { MarketShareResponse } from '../../api/types'
import { formatSEK, formatPct } from '../../utils/format'
import { Card, CardHeader, CardBody } from '../ui/Card'
import { Skeleton } from '../ui/Skeleton'
import { ErrorState } from '../ui/ErrorState'

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
          <div>
            <h2 className="text-sm font-semibold text-slate-800">Marknadsandel</h2>
            <p className="text-xs text-slate-500 mt-0.5">Andel av kategoriomsättning</p>
          </div>
          <div className="flex gap-1 bg-slate-50 border border-slate-100 rounded-lg p-0.5">
            {CATEGORIES.map(c => (
              <button
                key={c}
                onClick={() => onCategoryChange(c)}
                className={`text-xs px-2.5 py-1.5 rounded-md font-medium transition-colors ${
                  selectedCategory === c
                    ? 'bg-white text-slate-900 shadow-sm border border-slate-100'
                    : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                {c}
              </button>
            ))}
          </div>
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
          <div className="flex items-center gap-6">
            {/* Donut + pct label */}
            <div className="shrink-0 flex flex-col items-center">
              <ResponsiveContainer width={148} height={148}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={44}
                    outerRadius={68}
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
                    contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <p className="-mt-1 text-2xl font-bold text-slate-900 tabular-nums leading-none">
                {formatPct(data.market_share_pct)}
              </p>
              <p className="text-xs text-slate-500 mt-1">Vår andel</p>
            </div>

            {/* Stats */}
            <div className="flex-1 space-y-3">
              <div>
                <p className="text-xs font-medium text-slate-500">Vår omsättning</p>
                <p className="text-lg font-bold text-slate-900 tabular-nums mt-0.5">{formatSEK(data.supplier_revenue)}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-slate-500">Kategoritotal</p>
                <p className="text-lg font-bold text-slate-900 tabular-nums mt-0.5">{formatSEK(data.category_total_revenue)}</p>
              </div>
              <div className="rounded-lg bg-slate-50/80 border border-slate-100 px-3 py-2">
                <p className="text-xs text-slate-500">
                  {data.competitor_count} konkurrenter · enbart aggregat
                </p>
                <p className="text-sm font-semibold text-slate-700 tabular-nums mt-0.5">
                  {formatSEK(data.competitor_aggregate_revenue)}
                </p>
              </div>
            </div>
          </div>
        )}
      </CardBody>
    </Card>
  )
}
