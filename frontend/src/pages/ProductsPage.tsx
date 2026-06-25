import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { AuthUser, ProductAssortmentResponse } from '../api/types'
import { formatSEK, formatSEKUnitPrice, formatNumber, formatShortDateSv } from '../utils/format'
import { Card, CardBody } from '../components/ui/Card'
import { Skeleton } from '../components/ui/Skeleton'
import { ErrorState } from '../components/ui/ErrorState'

interface ProductsPageProps {
  user: AuthUser
}

function productCountLabel(count: number): string {
  return count === 1 ? '1 produkt' : `${count} produkter`
}

export function ProductsPage({ user }: ProductsPageProps) {
  const [data, setData] = useState<ProductAssortmentResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  const load = () => {
    setLoading(true)
    setError(null)
    api.getProductAssortment()
      .then(setData)
      .catch(e => setError(String(e.message ?? e)))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  const filteredProducts = useMemo(() => {
    const products = data?.products ?? []
    const q = search.trim().toLowerCase()
    if (!q) return products
    return products.filter(p => p.product_name.toLowerCase().includes(q))
  }, [data, search])

  const dateNote = data?.date_range
    ? `${formatShortDateSv(data.date_range.start)} – ${formatShortDateSv(data.date_range.end)}`
    : null

  return (
    <div className="overview-page overview-content-stage space-y-6 pb-4">
      <header className="overview-hero-zone">
        <div className="overview-hero-atmosphere" aria-hidden />
        <div className="overview-hero-content">
          <div className="overview-hero-heading min-w-0">
            <p className="overview-hero-eyebrow">SORTIMENT</p>
            <h1 className="overview-hero-title">Produkter</h1>
            <p className="overview-hero-subtitle">
              Översikt över ditt sortiment och försäljningsutfall
            </p>
            <div className="overview-hero-meta">
              <span className="overview-hero-supplier">{user.supplier_name}</span>
              <span className="overview-hero-dot" aria-hidden>·</span>
              <span className="overview-hero-tag">Baserat på tillgänglig försäljningsdata</span>
              {dateNote && (
                <>
                  <span className="overview-hero-dot" aria-hidden>·</span>
                  <span className="overview-hero-date">{dateNote}</span>
                </>
              )}
            </div>
          </div>
        </div>
      </header>

      <Card variant="dashboard">
        <CardBody className="!p-0">
          <div className="products-table-toolbar px-5 pt-5 pb-4 border-b border-workspace-border/40">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <label className="products-search-field relative block w-full sm:max-w-xs">
                <span className="sr-only">Sök produkt</span>
                <svg
                  className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-theme-faint pointer-events-none"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1.75}
                  viewBox="0 0 24 24"
                  aria-hidden
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M11 18a7 7 0 100-14 7 7 0 000 14z" />
                </svg>
                <input
                  type="search"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder="Sök produkt"
                  className="products-search-input w-full"
                />
              </label>
              {!loading && data && (
                <p className="text-sm text-theme-muted tabular-nums shrink-0">
                  {productCountLabel(filteredProducts.length)}
                  {search.trim() && filteredProducts.length !== data.products.length && (
                    <span className="text-theme-faint"> av {data.products.length}</span>
                  )}
                </p>
              )}
            </div>
            <p className="mt-3 text-[11px] text-theme-faint leading-snug">
              Pris avser genomsnittligt försäljningspris per såld enhet under vald period.
            </p>
          </div>

          {loading ? (
            <div className="px-5 py-4 space-y-3">
              {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-11 w-full" />)}
            </div>
          ) : error || !data ? (
            <div className="px-5 py-8">
              <ErrorState message={error ?? 'Kunde inte hämta produktdata.'} onRetry={load} />
            </div>
          ) : filteredProducts.length === 0 ? (
            <p className="px-5 py-12 text-sm text-theme-muted text-center">
              {search.trim() ? 'Inga produkter matchar sökningen' : 'Inga produkter i sortimentet'}
            </p>
          ) : (
            <div className="products-table-scroll">
              <div className="products-table" role="table">
                <div className="products-table-head" role="rowgroup">
                  <div className="products-table-grid products-table-head-row" role="row">
                    <div className="products-cell products-cell-product" role="columnheader">Produkt</div>
                    <div className="products-cell products-cell-num" role="columnheader">
                      Genomsnittligt försäljningspris / enhet
                    </div>
                    <div className="products-cell products-cell-num products-cell-compact" role="columnheader">
                      Sålda enheter
                    </div>
                    <div className="products-cell products-cell-num products-cell-compact" role="columnheader">
                      Omsättning
                    </div>
                    <div className="products-cell products-cell-action products-cell-compact" role="columnheader">
                      <span className="sr-only">Åtgärd</span>
                    </div>
                  </div>
                </div>
                <div className="products-table-body" role="rowgroup">
                  {filteredProducts.map(product => (
                    <div key={product.product_id} className="products-table-grid products-table-row" role="row">
                      <div className="products-cell products-cell-product" role="cell">
                        <span className="products-table-name">{product.product_name}</span>
                      </div>
                      <div className="products-cell products-cell-num" role="cell">
                        <span className="products-table-price tabular-nums">
                          {formatSEKUnitPrice(product.average_sale_price_per_unit)}
                        </span>
                      </div>
                      <div className="products-cell products-cell-num" role="cell">
                        <span className="products-table-metric tabular-nums">
                          {formatNumber(product.units)}
                        </span>
                      </div>
                      <div className="products-cell products-cell-num" role="cell">
                        <span className="products-table-revenue tabular-nums">
                          {formatSEK(product.revenue)}
                        </span>
                      </div>
                      <div className="products-cell products-cell-action" role="cell">
                        <Link to="/assistant" className="products-analyze-link">
                          Analysera
                          <span aria-hidden className="ml-0.5">→</span>
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
