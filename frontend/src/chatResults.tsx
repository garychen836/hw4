// Product matches from the latest chat answer, shared so the page (not just the chat bubble) can show them.
// Kept in sessionStorage so they survive a refresh or opening a product page and coming back.
import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import type { Product } from './api'

// owner: whose conversation asked for these results ('guest' or 'u<user id>'); they only show in that conversation.
export type ChatResults = {
  title: string
  question: string
  products: Product[]
  at: number
  owner: string
  query?: string | null // the agent's search, for "See all N matches"
  total?: number | null
}

type State = {
  results: ChatResults | null
  show: (r: Omit<ChatResults, 'at'>) => void
  clear: () => void
}

const KEY = 'cc-chat-results'
const Ctx = createContext<State | null>(null)

function load(): ChatResults | null {
  try {
    const raw = sessionStorage.getItem(KEY)
    const r = raw ? (JSON.parse(raw) as ChatResults) : null
    return r && r.owner ? r : null // results saved before owners existed are dropped
  } catch {
    return null
  }
}

export function ChatResultsProvider({ children }: { children: ReactNode }) {
  const [results, setResults] = useState<ChatResults | null>(load)

  const show = useCallback((r: Omit<ChatResults, 'at'>) => {
    const next = { ...r, at: Date.now() }
    setResults(next)
    sessionStorage.setItem(KEY, JSON.stringify(next))
  }, [])

  const clear = useCallback(() => {
    setResults(null)
    sessionStorage.removeItem(KEY)
  }, [])

  return <Ctx.Provider value={{ results, show, clear }}>{children}</Ctx.Provider>
}

export function useChatResults(): State {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useChatResults must be used inside <ChatResultsProvider>')
  return ctx
}
