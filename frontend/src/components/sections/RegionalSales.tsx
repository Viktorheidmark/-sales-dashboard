import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Cell,
} from 'recharts'
import type { RegionsResponse } from '../../api/types'
import { formatSEK, formatNumber } from '../../utils/format'
import { Card, CardHeader, CardBody } from '../ui/Card'
import { ChartSkeleton } from '../ui/Skeleton'
import { ErrorState } from '../ui/ErrorState'

interface RegionalSalesProps {
  data: RegionsResponse | null
  loading: boolean
  error: string | null
  onRetry: () => void
}

function RegionTooltip({ active, payload }: {
  active?: boolean
  payload?: { payload: { region: string; revenue: number; orders: number } }[]
}) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-white border border-slate-100 shadow-lg rounded-lg px-3 py-2 text-sm">
      <p className="font-semibold text-slate-800">{d.region}</p>
      <p className="text-brand-600 font-medium">{formatSEK(d.revenue)}</p>
      <p className="text-slate-400 text-xs mt-0.5">{formatNumber(d.orders)} ordrar</p>
    </div>
  )
}

export function RegionalSales({ data, loading, error, onRetry }: RegionalSalesProps) {
  if (loading) return <ChartSkeleton height={220} />

  if (error || !data) {
    return (
      <Card>
        <CardHeader><h2 className="text-sm font-semibold text-slate-800">Försäljning per region</h2></CardHeader>
        <CardBody><ErrorState message={error ?? 'Kunde inte hämta data.'} onRetry={onRetry} /></CardBody>
      </Card>
    )
  }

  const chartData = data.regions.map(r => ({
    region: r.region,
    revenue: r.revenue ?? 0,
    orders: r.orders,
  }))

  const maxRev = chartData[0]?.revenue ?? 1

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">Försäljning per region</h2>
            <p className="text-xs text-slate-400 mt-0.5">Rankade efter omsättning</p>
          </div>
          {data.regions[0] && (
            <span className="text-xs text-brand-600 font-medium bg-brand-50 border border-brand-100 px-2 py-1 rounded-md">
              {data.regions[0].region} #1
            </span>
          )}
        </div>
      </CardHeader>
      <CardBody>
        {chartData.length === 0 ? (
          <p className="text-sm text-slate-400 text-center py-8">Inga regionala försäljningsdata för vald period</p>
        ) : (
          <>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis
                  dataKey="region"
                  tick={{ fontSize: 11, fill: '#94a3b8' }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  tickFormatter={v => formatSEK(v)}
                  tick={{ fontSize: 11, fill: '#94a3b8' }}
                  tickLine={false}
                  axisLine={false}
                  width={68}
                />
                <Tooltip content={<RegionTooltip />} />
                <Bar dataKey="revenue" radius={[3, 3, 0, 0]} maxBarSize={52}>
                  {chartData.map((entry, i) => (
                    <Cell key={entry.region} fill={i === 0 ? '#4169e1' : '#dde3f7'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>

            {/* Ranked list — clearly connected to chart above */}
            <div className="mt-3 pt-3 border-t border-slate-100">
              <div className="grid grid-cols-[1rem_1fr_4rem_5rem] gap-x-3 mb-1.5 px-1">
                <span />
                <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">Region</span>
                <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide text-right">Ordrar</span>
                <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide text-right">Omsättning</span>
              </div>
              {data.regions.map((r, i) => (
                <div
                  key={r.region}
                  className="grid grid-cols-[1rem_1fr_4rem_5rem] gap-x-3 items-center py-2 border-b border-slate-50 last:border-0 px-1"
                >
                  <span className={`text-xs font-bold leading-none ${i === 0 ? 'text-brand-500' : 'text-slate-300'}`}>{i + 1}</span>
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-sm font-medium text-slate-800 truncate">{r.region}</span>
                    <div className="h-px flex-1 bg-slate-100 overflow-hidden max-w-[3rem]">
                      <div
                        className="h-full bg-brand-300"
                        style={{ width: `${maxRev > 0 ? ((r.revenue ?? 0) / maxRev) * 100 : 0}%` }}
                      />
                    </div>
                  </div>
                  <span className="text-xs text-slate-500 tabular-nums text-right">{formatNumber(r.orders)}</span>
                  <span className="text-sm font-semibold text-slate-900 tabular-nums text-right">{formatSEK(r.revenue)}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </CardBody>
    </Card>
  )
}
