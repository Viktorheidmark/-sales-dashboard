import type {
  OverviewResponse,
  RegionsResponse,
  TopProductsResponse,
} from '../api/types'
import type { DatePreset } from './dateRange'

const STABLE_THRESHOLD_PCT = 5

function describeSalesTrend(
  overview: OverviewResponse,
  preset: DatePreset,
): string {
  if (preset === 'all') {
    return 'Försäljningen sammanfattar hela den tillgängliga historiken.'
  }

  const current = overview.total_revenue
  const previous = overview.prev_total_revenue

  if (current == null || previous == null || previous <= 0) {
    return 'Försäljningen är jämn över vald period.'
  }

  const changePct = ((current - previous) / previous) * 100

  if (Math.abs(changePct) < STABLE_THRESHOLD_PCT) {
    return 'Försäljningen är stabil över perioden.'
  }

  if (changePct >= STABLE_THRESHOLD_PCT) {
    return 'Försäljningen visar positiv utveckling över perioden.'
  }

  return 'Försäljningen har en svagare utveckling över perioden.'
}

function describeDrivers(
  topProducts: TopProductsResponse | null,
  regions: RegionsResponse | null,
): string | null {
  const topProduct = topProducts?.products?.[0]
  const topRegion = regions?.regions?.[0]

  if (topProduct && topRegion) {
    return `${topProduct.product_name} driver omsättningen, medan ${topRegion.region} är den starkaste regionen.`
  }

  if (topProduct) {
    return `${topProduct.product_name} driver omsättningen.`
  }

  if (topRegion) {
    return `${topRegion.region} är den starkaste regionen.`
  }

  return null
}

export function buildOverviewInsightText(
  overview: OverviewResponse | null,
  topProducts: TopProductsResponse | null,
  regions: RegionsResponse | null,
  preset: DatePreset,
): string | null {
  if (!overview) return null

  const trend = describeSalesTrend(overview, preset)
  const drivers = describeDrivers(topProducts, regions)

  if (drivers) {
    return `${trend} ${drivers}`
  }

  return `${trend} Data över produkter och regioner kompletterar bilden nedan.`
}

export function overviewInsightStatusLabel(generatedAt: string | undefined): string {
  if (!generatedAt) return 'Analys klar'

  const today = new Date().toISOString().slice(0, 10)
  const generatedDate = generatedAt.slice(0, 10)

  return generatedDate === today ? 'Uppdaterad idag' : 'Analys klar'
}
