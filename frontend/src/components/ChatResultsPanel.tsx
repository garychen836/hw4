import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../auth'
import { useChatResults } from '../chatResults'
import ProductCard from './ProductCard'

// "Matching items from your chat": the agent's product matches rendered on the page as regular product cards.
// Each card is the same ProductCard used on the Products page, so clicking it opens the single-item page.
const ACCOUNT_PAGES = new Set(['/login', '/signup'])

export default function ChatResultsPanel() {
  const { results, clear } = useChatResults()
  const { pathname, search } = useLocation()
  const onProductPage = pathname.startsWith('/products/')
  const [collapsed, setCollapsed] = useState(onProductPage)
  const ref = useRef<HTMLElement>(null)
  const lastSeen = useRef(results?.at) // results restored on page load are not "new"
  const [fresh, setFresh] = useState(false) // animate only when the chat just returned new results

  // On a single-item page the product's own large image and details come first, and after "See all" the
  // Products page already lists every match; in both cases collapse to a slim bar.
  const showingAllMatches =
    pathname === '/products' && !!results?.query && new URLSearchParams(search).get('q') === results.query
  useEffect(() => {
    setCollapsed(onProductPage || showingAllMatches)
  }, [pathname, search]) // eslint-disable-line react-hooks/exhaustive-deps

  // New results from the chat: expand and bring them into view.
  useEffect(() => {
    if (!results || results.at === lastSeen.current) return
    lastSeen.current = results.at
    setFresh(true)
    setTimeout(() => setFresh(false), 1200) // after the slide-in and staggered card animations
    setCollapsed(false)
    ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [results?.at]) // eslint-disable-line react-hooks/exhaustive-deps

  // Only show results the current conversation asked for (not a previous user's or a reset chat's).
  const { user, loading: authLoading } = useAuth()
  const owner = user ? `u${user.id}` : 'guest'
  const stale = !authLoading && results !== null && results.owner !== owner
  useEffect(() => {
    if (stale) clear()
  }, [stale, clear])

  if (!results || results.products.length === 0 || authLoading || stale) return null
  // Account pages show only the form; results stay saved and reappear on shopping pages.
  if (ACCOUNT_PAGES.has(pathname)) return null

  return (
    <section
      ref={ref}
      className={`chat-results ${collapsed ? 'collapsed' : ''} ${fresh ? 'fresh' : ''}`}
      aria-label="Matching items from your chat"
      key={results.at}
    >
      <div className="container">
        <div className="chat-results-head">
          <div>
            <p className="kicker">💬 Matching items from your chat</p>
            <h2>{results.title}</h2>
            <p className="chat-results-q">
              You asked: “{results.question}” · {results.products.length}{' '}
              {results.products.length === 1 ? 'item' : 'items'}
              {results.query && results.total && results.total > results.products.length && (
                <>
                  {' · '}
                  <Link to={`/products?q=${encodeURIComponent(results.query)}`} className="link-arrow">
                    See all {results.total} matches →
                  </Link>
                </>
              )}
            </p>
          </div>
          <div className="chat-results-actions">
            <button className="btn btn-secondary btn-sm" onClick={() => setCollapsed((c) => !c)}>
              {collapsed ? `Show ${results.products.length} items` : 'Hide'}
            </button>
            <button className="btn btn-secondary btn-sm" onClick={clear} aria-label="Clear chat results">
              Clear
            </button>
          </div>
        </div>
        {!collapsed && (
          <div className={`product-grid chat-results-grid ${onProductPage ? 'compact' : ''}`}>
            {results.products.map((p, i) => (
              <div key={p.product_id} className="chat-results-item" style={{ animationDelay: `${i * 60}ms` }}>
                <ProductCard product={p} />
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
