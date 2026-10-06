import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { CATEGORIES, COLLECTIONS, categoryOf, fetchProducts, searchProductIds, type Product } from '../api'
import ProductCard from '../components/ProductCard'
import { setProductFilters } from '../pageContext'

type Sort = 'relevance' | 'name' | 'price-asc' | 'price-desc'

function SkeletonGrid() {
  return (
    <div className="product-grid" aria-hidden="true">
      {Array.from({ length: 8 }, (_, i) => (
        <div key={i} className="skeleton-card">
          <div className="skeleton skeleton-img" />
          <div className="skeleton skeleton-line" />
          <div className="skeleton skeleton-line short" />
        </div>
      ))}
    </div>
  )
}

export default function Products() {
  const [products, setProducts] = useState<Product[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [params] = useSearchParams()
  const collection = COLLECTIONS.find((c) => c.key === params.get('collection')) ?? null
  const [category, setCategory] = useState(params.get('category') ?? 'All')
  const [query, setQuery] = useState(params.get('q') ?? '')
  const [sort, setSort] = useState<Sort>(params.get('q') ? 'relevance' : 'name')
  // Server-side search (same ranking, synonyms, and plurals as the chat agent): matching ids, best first.
  const [rank, setRank] = useState<string[] | null>(null)
  const [searching, setSearching] = useState(false)

  // Follow links like /products?category=Hoodies or ?q=hockey (e.g. from the chat) even when already on this page.
  useEffect(() => {
    setCategory(params.get('category') ?? 'All')
    setQuery(params.get('q') ?? '')
  }, [params])

  useEffect(() => {
    fetchProducts()
      .then(setProducts)
      .catch(() => setError('We could not load the catalogue. Is the backend running?'))
      .finally(() => setLoading(false))
  }, [])

  // Debounced search: wait until typing pauses for 250 ms, ignore out-of-date responses.
  useEffect(() => {
    const q = query.trim()
    if (!q) {
      setRank(null)
      setSearching(false)
      return
    }
    setSearching(true)
    let cancelled = false
    const t = setTimeout(() => {
      searchProductIds(q)
        .then((ids) => !cancelled && setRank(ids))
        .catch(() => !cancelled && setRank([]))
        .finally(() => !cancelled && setSearching(false))
    }, 250)
    return () => {
      cancelled = true
      clearTimeout(t)
    }
  }, [query])

  useEffect(() => {
    if (query.trim()) setSort((s) => (s === 'name' ? 'relevance' : s))
    else setSort((s) => (s === 'relevance' ? 'name' : s))
  }, [query])

  // Tell the chat what the shopper is browsing.
  useEffect(() => {
    setProductFilters({ search: query, category, collection: collection?.key ?? null })
    return () => setProductFilters({})
  }, [query, category, collection])

  const shown = useMemo(() => {
    const order = rank ? new Map(rank.map((id, i) => [id, i])) : null
    const list = products.filter((p) => {
      if (collection && !collection.match(p)) return false
      if (category !== 'All' && categoryOf(p) !== category) return false
      if (order && !order.has(p.product_id)) return false
      return true
    })
    if (sort === 'price-asc') return [...list].sort((a, b) => a.price - b.price || a.name.localeCompare(b.name))
    if (sort === 'price-desc') return [...list].sort((a, b) => b.price - a.price || a.name.localeCompare(b.name))
    if (sort === 'relevance' && order) return [...list].sort((a, b) => order.get(a.product_id)! - order.get(b.product_id)!)
    return list
  }, [products, collection, category, rank, sort])

  const busy = loading || (searching && rank === null)

  return (
    <div className="container section">
      <h1 className="page-title">{collection ? collection.title : 'All products'}</h1>
      {collection && (
        <p className="collection-note">
          {collection.blurb}{' '}
          <Link to="/products" className="link-arrow">
            Show all products ×
          </Link>
        </p>
      )}

      <div className="filters">
        <div className="chips" role="group" aria-label="Category">
          {['All', ...CATEGORIES].map((c) => (
            <button
              key={c}
              className={`chip ${category === c ? 'active' : ''}`}
              aria-pressed={category === c}
              onClick={() => setCategory(c)}
            >
              {c}
            </button>
          ))}
        </div>
        <div className="filter-controls">
          <input
            type="search"
            placeholder="Search (e.g. hockey, Saybrook, gray tee)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search products"
          />
          <select value={sort} onChange={(e) => setSort(e.target.value as Sort)} aria-label="Sort">
            {query.trim() && <option value="relevance">Sort: Best match</option>}
            <option value="name">Sort: Name</option>
            <option value="price-asc">Price: low to high</option>
            <option value="price-desc">Price: high to low</option>
          </select>
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {busy && !error && <SkeletonGrid />}
      {!busy && !error && (
        <>
          <p className="muted result-count" aria-live="polite">
            {shown.length} {shown.length === 1 ? 'product' : 'products'}
            {query.trim() && ` for “${query.trim()}”`}
            {searching && ' · updating…'}
          </p>
          {shown.length > 0 ? (
            <div className="product-grid">
              {shown.map((p) => (
                <ProductCard key={p.product_id} product={p} />
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <h2>No products match{query.trim() ? ` “${query.trim()}”` : ''}.</h2>
              <p>Try a broader word (like “hoodie” or “navy”), clear the filters, or ask our assistant to help you find it.</p>
              <div className="empty-actions">
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => {
                    setQuery('')
                    setCategory('All')
                  }}
                >
                  Clear search and filters
                </button>
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() =>
                    window.dispatchEvent(
                      new CustomEvent('open-chat', { detail: { ask: query.trim() ? `Do you have anything like "${query.trim()}"?` : undefined } }),
                    )
                  }
                >
                  Ask our assistant
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
