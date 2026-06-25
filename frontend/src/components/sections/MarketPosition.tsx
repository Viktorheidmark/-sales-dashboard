import { PieChart, Pie, Cell, Tooltip } from 'recharts'
import type { MarketShareResponse } from '../../api/types'
import { formatSEK } from '../../utils/format'
import { useChartTheme } from '../../utils/chartTheme'
import { useTenantBranding } from '../../context/TenantBrandingContext'
import {
  buildMarketPositionInsight,
  formatSupplierRankLine,
} from '../../utils/marketPositionInsight'
import { Card, CardHeader, CardBody } from '../ui/Card'
import { Skeleton } from '../ui/Skeleton'
import { ErrorState } from '../ui/ErrorState'

interface MarketPositionProps {
  data: MarketShareResponse | null
  loading: boolean
  error: string | null
  onRetry: () => void
  supplierCategory: string
  periodContextLabel?: string
}

function formatSharePct(value: number): string {
  return `${value.toLocaleString('sv-SE', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} %`
}

function ComparisonRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="dashboard-list-row flex items-center justify-between gap-3 py-2">
      <span className="text-sm text-theme-muted">{label}</span>
      <span className="text-sm font-semibold text-theme-heading tabular-nums shrink-0">{value}</span>
    </div>
  )
}

export function MarketPosition({
  data,
  loading,
  error,
  onRetry,
  supplierCategory,
  periodContextLabel,
}: MarketPositionProps) {
  const { chart, chartTooltipStyle } = useChartTheme()
  const { chartPrimary } = useTenantBranding()

  const pieData = data
    ? [
        { name: 'Din andel', value: data.supplier_revenue, color: chartPrimary },
        {
          name: 'Övriga leverantörer',
          value: data.competitor_aggregate_revenue ?? 0,
          color: chart.pieMuted,
        },
      ]
    : []

  const rankLine = data ? formatSupplierRankLine(data.supplier_rank, data.total_suppliers) : null
  const insight = data ? buildMarketPositionInsight(data) : null

  const subtitle = periodContextLabel
    ? `Andel av kategoriförsäljning · ${periodContextLabel}`
    : 'Andel av kategoriförsäljning'

  return (
    <Card variant="dashboard">
      <CardHeader>
        <div>
          <h2 className="dashboard-panel-title">Marknadsposition</h2>
          <p className="dashboard-panel-subtitle">{subtitle}</p>
          <p className="text-[11px] text-theme-faint mt-0.5">{supplierCategory}</p>
        </div>
      </CardHeader>
      <CardBody>
        {loading ? (
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              <Skeleton className="w-24 h-24 rounded-full shrink-0" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-8 w-24" />
                <Skeleton className="h-4 w-32" />
              </div>
            </div>
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-4 w-full" />
          </div>
        ) : error || !data ? (
          <ErrorState message={error ?? 'Kunde inte hämta data.'} onRetry={onRetry} />
        ) : data.category_total_revenue <= 0 ? (
          <p className="text-sm text-theme-muted text-center py-8">
            Ingen kategoridata för vald period
          </p>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              <div className="relative shrink-0">
                <PieChart width={108} height={108}>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={34}
                    outerRadius={50}
                    dataKey="value"
                    startAngle={90}
                    endAngle={-270}
                    strokeWidth={0}
                  >
                    {pieData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: number) => formatSEK(v)} contentStyle={chartTooltipStyle} />
                </PieChart>
              </div>

              <div className="flex-1 min-w-0 space-y-3">
                <div>
                  <p className="text-2xl font-bold text-theme-heading tabular-nums leading-none">
                    {formatSharePct(data.market_share_pct)}
                  </p>
                  <p className="text-xs text-theme-muted mt-1">Din andel</p>
                </div>
                <div>
                  <p className="text-sm font-semibold text-theme-heading tabular-nums leading-tight">
                    {formatSEK(data.category_total_revenue)}
                  </p>
                  <p className="text-[11px] text-theme-muted">Kategoriomsättning</p>
                </div>
              </div>
            </div>

            <div className="border-t border-workspace-border/40 pt-1">
              <ComparisonRow label="Din försäljning" value={formatSEK(data.supplier_revenue)} />
              <ComparisonRow
                label="Övriga leverantörer"
                value={formatSEK(data.competitor_aggregate_revenue ?? 0)}
              />
              {rankLine && (
                <p className="text-[11px] text-theme-faint leading-snug pt-1 pb-0.5">
                  {rankLine}
                </p>
              )}
            </div>

            {insight && (
              <p className="text-[11px] text-theme-muted leading-snug border-t border-workspace-border/30 pt-3">
                {insight}
              </p>
            )}
          </div>
        )}
      </CardBody>
    </Card>
  )
}
