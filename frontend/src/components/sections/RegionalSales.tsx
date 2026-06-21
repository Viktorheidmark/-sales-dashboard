import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Cell,
} from 'recharts'
import type { RegionsResponse } from '../../api/types'
import { formatSEK, formatNumber } from '../../utils/format'
import { Card, CardHeader, CardBody } from '../ui/Card'
import { ChartSkeleton } from '../ui/Skeleton'
import { ErrorState } from '../ui/ErrorState'
import { MetaFooter } from '../ui/MetaFooter'

interface RegionalSalesProps {
  data: RegionsResponse | null
  loading: boolean
  error: string | null
  onRetry: () => void
}

function RegionTooltip({ active, payload }: { active?: boolean; payload?: { payload: { region: string; revenue: number; orders: number } }[] }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-white border border-zinc-200 shadow-lg rounded-lg px-3 py-2 text-sm">
      <p className="font-semibold text-zinc-800">{d.region}</p>
      <p className="text-brand-600">{formatSEK(d.revenue)}</p>
      <p className="text-zinc-500 text-xs">{formatNumber(d.orders)} orders</p>
    </div>
  )
}

export function RegionalSales({ data, loading, error, onRetry }: RegionalSalesProps) {
  if (loading) return <ChartSkeleton height={200} />

  if (error || !data) {
    return (
      <Card>
        <CardHeader><h2 className="text-sm font-semibold text-zinc-700">Sales by region</h2></CardHeader>
        <CardBody><ErrorState message={error ?? 'No data'} onRetry={onRetry} /></CardBody>
      </Card>
    )
  }

  const chartData = data.regions.map(r => ({
    region: r.region,
    revenue: r.revenue ?? 0,
    orders: r.orders,
    rank: r.rank,
  }))

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-zinc-700">Sales by region</h2>
          {data.regions[0] && (
            <span className="text-xs bg-brand-50 text-brand-600 font-medium px-2 py-0.5 rounded-full">
              #{1} {data.regions[0].region}
            </span>
          )}
        </div>
      </CardHeader>
      <CardBody>
        {chartData.length === 0 ? (
          <p className="text-sm text-zinc-400 text-center py-6">No regional data</p>
        ) : (
          <>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" vertical={false} />
                <XAxis
                  dataKey="region"
                  tick={{ fontSize: 11, fill: '#a1a1aa' }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  tickFormatter={v => formatSEK(v)}
                  tick={{ fontSize: 11, fill: '#a1a1aa' }}
                  tickLine={false}
                  axisLine={false}
                  width={72}
                />
                <Tooltip content={<RegionTooltip />} />
                <Bar dataKey="revenue" radius={[4, 4, 0, 0]}>
                  {chartData.map((entry, i) => (
                    <Cell
                      key={entry.region}
                      fill={i === 0 ? '#4169e1' : '#c7d2fe'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>

            {/* Detail table */}
            <div className="mt-4 space-y-2">
              {data.regions.map((r, i) => (
                <div key={r.region} className="flex items-center gap-3 text-sm">
                  <span className="text-xs text-zinc-400 w-5 shrink-0">#{i + 1}</span>
                  <span className="font-medium text-zinc-800 flex-1">{r.region}</span>
                  <span className="text-xs text-zinc-400">{formatNumber(r.orders)} orders</span>
                  <span className="font-semibold text-zinc-900 tabular-nums">{formatSEK(r.revenue)}</span>
                </div>
              ))}
            </div>
          </>
        )}
        <MetaFooter
          source={data.source}
          generatedAt={data.generated_at}
          rowCount={data.row_count}
        />
      </CardBody>
    </Card>
  )
}
