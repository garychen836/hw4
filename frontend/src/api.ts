import type { PageContext } from './pageContext'

// Types and fetch helpers for the FastAPI backend (proxied by Vite).

export type SizeStock = { size: string; quantity: number }

export type Product = {
  product_id: string
  name: string
  garment_type: string
  description: string
  colors: string[]
  search_tags: string[]
  image_url: string
  price: number
  total_stock: number
  inventory?: SizeStock[]
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(res.status === 404 ? 'Not found' : `Request failed (${res.status})`)
  return res.json() as Promise<T>
}

export const fetchProducts = () => getJson<Product[]>('/api/products')
export const fetchProduct = (id: string) => getJson<Product>(`/api/products/${encodeURIComponent(id)}`)

export type NavigateAction = {
  type: 'product' | 'products'
  product_id?: string | null
  search?: string | null
  collection?: string | null
}

export type ChatTurn = { role: 'user' | 'assistant'; content: string }

export type ChatReply = {
  message_id: number | null
  reply_id: string
  reply: string
  products: Product[]
  results_title: string | null
  results_query: string | null
  results_total: number | null
  navigate: NavigateAction | null
  suggestions: string[]
  checks: string[]
  usage: { requests: number; input_tokens: number; output_tokens: number; tool_calls: number; duration_ms: number; model: string }
}

async function errorText(res: Response): Promise<string> {
  try {
    const body = await res.json()
    if (typeof body.detail === 'string') return body.detail
  } catch {
    /* ignore */
  }
  return `Request failed (${res.status})`
}

export async function sendChat(message: string, history: ChatTurn[], page: PageContext): Promise<ChatReply> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify({ message, history, page }),
  })
  if (!res.ok) throw new Error(await errorText(res))
  return res.json()
}

export async function fetchChatHistory(): Promise<
  { role: 'user' | 'assistant'; content: string; products: Product[]; reply_id: string | null; created_at: string }[]
> {
  const res = await fetch('/api/chat/history', { credentials: 'same-origin' })
  if (!res.ok) return []
  return (await res.json()).messages
}

export async function sendFeedback(body: {
  reply_id: string
  helpful?: boolean
  accurate?: boolean
  comment?: string
}): Promise<void> {
  await fetch('/api/chat/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify(body),
  })
}

export async function searchProductIds(q: string): Promise<string[]> {
  const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`)
  if (!res.ok) throw new Error(`Search failed (${res.status})`)
  return (await res.json()).product_ids as string[]
}

export const formatPrice = (n: number) => `$${n.toFixed(2)}`

// Group the 22 messy garment_type labels into a few shopper-friendly categories.
export function categoryOf(p: Product): string {
  const t = `${p.garment_type} ${p.name}`.toLowerCase()
  if (t.includes('jacket') || t.includes('full-zip') || t.includes('full zip')) return 'Jackets & Full-Zips'
  if (t.includes('quarter-zip') || t.includes('1 4 zip')) return 'Quarter-Zips'
  if (t.includes('hood')) return 'Hoodies'
  if (t.includes('crewneck') || t.includes('mockneck') || t.includes('sweater')) return 'Crewnecks & Sweaters'
  if (t.includes('shirt') || t.includes('tee')) return 'T-Shirts & Tops'
  return 'Other'
}

export const CATEGORIES = [
  'Hoodies',
  'Crewnecks & Sweaters',
  'Quarter-Zips',
  'Jackets & Full-Zips',
  'T-Shirts & Tops',
]

// Themed collections for the home page and /products?collection=<key>, based on product IDs.
const COLLEGES =
  /(benjamin-franklin|berkeley|branford|davenport|ezra-stiles|grace-hopper|jonathan-edwards|morse|pauli-murray|pierson|saybrook|silliman|timothy-dwight|trumbull)/
const SPORTS =
  /(baseball|basketball|football|hockey|soccer|tennis|golf|lacrosse|sailing|fencing|squash|diving|swimming|volleyball|track|field-hockey|crew-left|yale-sports|tri-blend-sports)/
const FAMILY = /yale-(mom|dad|grandpa|grandma|brother|uncle|aunt|cousin)/
const SCHOOLS = /(school-of|law-school|divinity|forest-school)/

export type Collection = { key: string; title: string; blurb: string; cover: string; match: (p: Product) => boolean }

export const COLLECTIONS: Collection[] = [
  {
    key: 'colleges',
    title: 'Residential Colleges',
    blurb: 'Crests and colors from across the colleges.',
    cover: 'davenport-college-crewneck',
    match: (p) => COLLEGES.test(p.product_id),
  },
  {
    key: 'sports',
    title: 'Varsity Sports',
    blurb: 'Rep the Bulldogs, from hockey to sailing.',
    cover: 'ice-hockey-left-chest-hoodie',
    match: (p) => SPORTS.test(p.product_id) && !COLLEGES.test(p.product_id),
  },
  {
    key: 'family',
    title: 'Yale Family',
    blurb: 'For proud moms, dads, grandparents, and more.',
    cover: 'yale-mom-crewneck',
    match: (p) => FAMILY.test(p.product_id),
  },
  {
    key: 'schools',
    title: 'Graduate & Professional',
    blurb: 'Law, Medicine, Management, Art, and beyond.',
    cover: 'school-of-art-1-4-zip',
    match: (p) => SCHOOLS.test(p.product_id),
  },
  {
    key: 'classics',
    title: 'Classic Yale',
    blurb: 'Bulldogs, arched wordmarks, and vintage favorites.',
    cover: 'district-vit-hoodie-vintage-bulldog',
    match: (p) => ![COLLEGES, SPORTS, FAMILY, SCHOOLS].some((re) => re.test(p.product_id)),
  },
]
