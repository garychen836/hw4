// What the shopper is looking at, sent to the agent with every chat message so it can resolve
// "this one", "in a different size", "the second one", etc.
// Pages write into this small store; the chat widget reads it when a message is sent (no re-renders needed).

export type PageContext = {
  path: string
  page_type: 'home' | 'products' | 'product' | 'about' | 'login' | 'signup' | 'other'
  product_id?: string | null
  selected_size?: string | null
  search?: string | null
  category?: string | null
  collection?: string | null
  results_title?: string | null
  results_product_ids?: string[]
}

const state: { product_id: string | null; selected_size: string | null; search: string | null; category: string | null; collection: string | null } = {
  product_id: null,
  selected_size: null,
  search: null,
  category: null,
  collection: null,
}

// Single-item page: which product is open and which size is selected.
export function setViewedProduct(productId: string | null, size: string | null = null) {
  state.product_id = productId
  state.selected_size = size
}

// Products page: the active search box text, category chip, and collection.
export function setProductFilters(f: { search?: string; category?: string; collection?: string | null }) {
  state.search = f.search?.trim() || null
  state.category = f.category && f.category !== 'All' ? f.category : null
  state.collection = f.collection || null
}

function pageType(pathname: string): PageContext['page_type'] {
  if (pathname === '/') return 'home'
  if (pathname === '/products') return 'products'
  if (pathname.startsWith('/products/')) return 'product'
  if (pathname === '/about') return 'about'
  if (pathname === '/login') return 'login'
  if (pathname === '/signup') return 'signup'
  return 'other'
}

export function currentPageContext(
  pathname: string,
  search: string,
  results: { title: string; products: { product_id: string }[] } | null,
): PageContext {
  const type = pageType(pathname)
  const ctx: PageContext = { path: (pathname + search).slice(0, 200), page_type: type }
  if (type === 'product') {
    ctx.product_id = state.product_id ?? decodeURIComponent(pathname.split('/')[2] ?? '')
    ctx.selected_size = state.selected_size
  }
  if (type === 'products') {
    ctx.search = state.search
    ctx.category = state.category
    ctx.collection = state.collection
  }
  if (results && results.products.length) {
    ctx.results_title = results.title.slice(0, 60)
    ctx.results_product_ids = results.products.slice(0, 12).map((p) => p.product_id)
  }
  return ctx
}
