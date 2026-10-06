import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { fetchChatHistory, formatPrice, sendChat, sendFeedback, type NavigateAction, type Product } from '../api'
import { useAuth } from '../auth'
import { useChatResults } from '../chatResults'
import BulldogAvatar from './BulldogAvatar'
import { currentPageContext } from '../pageContext'

// When the agent decides the shopper asked to go somewhere, take them there automatically.
// Set to false to only show a "Take me there" button instead.
const AUTO_NAVIGATE = true
const GUEST_HISTORY_TURNS = 8
const GUEST_KEY = 'cc-guest-chat' // guests keep their chat for this browser tab only

type Feedback = 'none' | 'down' | 'sent'

type Message = {
  role: 'user' | 'assistant'
  content: string
  products?: Product[]
  suggestions?: string[]
  navigate?: NavigateAction | null
  replyId?: string
  feedback?: Feedback
  failed?: string // the question to resend when a request failed
}

// Shown one after another while the agent works, so a 3-5 s wait feels like progress.
const PROGRESS_STEPS = ['Reading your question…', 'Searching the catalogue…', 'Checking sizes and stock…', 'Double-checking prices…']

// Starter questions that fit the page the shopper is on.
function pageStarters(pathname: string, search: string): string[] {
  if (pathname.startsWith('/products/'))
    return ['Is this in stock in my size?', 'Does it come in other colors?', 'Show me similar items']
  if (pathname === '/products') {
    const q = new URLSearchParams(search).get('q')
    if (q) return [`Help me choose from these ${q}`, `Cheapest ${q} in stock`, 'Gifts under $40']
    return ['What are your best sellers?', 'Navy hoodies in M', 'Gifts under $40']
  }
  return ['Navy hoodies in M', 'Gifts for my mom', 'Yale vs Harvard tee']
}

const GREETING: Message = {
  role: 'assistant',
  content: "Hi! I'm the Campus Customs assistant. Ask me about our Yale merch, sizes, prices, or what's in stock.",
  suggestions: ['Navy hoodies in M', 'Gifts for my mom', 'Yale vs Harvard tee'],
}

function loadGuestChat(): Message[] {
  try {
    const saved = sessionStorage.getItem(GUEST_KEY)
    return saved ? (JSON.parse(saved) as Message[]) : [GREETING]
  } catch {
    return [GREETING]
  }
}

function pathFor(nav: NavigateAction): string | null {
  if (nav.type === 'product' && nav.product_id) return `/products/${encodeURIComponent(nav.product_id)}`
  if (nav.type === 'products') {
    if (nav.collection) return `/products?collection=${encodeURIComponent(nav.collection)}`
    if (nav.search) return `/products?q=${encodeURIComponent(nav.search)}`
    return '/products'
  }
  return null
}

// Minimal, safe formatting for chat text: **bold** and "- " bullet lines (no HTML is ever injected).
function renderInline(text: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? <strong key={i}>{part.slice(2, -2)}</strong> : part,
  )
}

function ChatText({ text }: { text: string }) {
  const lines = text.split('\n')
  const out: React.ReactNode[] = []
  let bullets: string[] = []
  const flush = () => {
    if (bullets.length) {
      out.push(
        <ul key={`ul${out.length}`}>
          {bullets.map((b, i) => (
            <li key={i}>{renderInline(b)}</li>
          ))}
        </ul>,
      )
      bullets = []
    }
  }
  lines.forEach((line) => {
    const m = line.match(/^\s*[-*•]\s+(.*)$/)
    if (m) {
      bullets.push(m[1])
    } else {
      flush()
      if (line.trim()) out.push(<p key={`p${out.length}`}>{renderInline(line)}</p>)
    }
  })
  flush()
  return <>{out}</>
}

function ChatProductCard({ p }: { p: Product }) {
  const inStock = (p.inventory ?? []).filter((s) => s.quantity > 0).map((s) => s.size)
  return (
    <Link to={`/products/${p.product_id}`} className="chat-card">
      <img src={p.image_url} alt="" />
      <div>
        <strong>{p.name}</strong>
        <span className="chat-card-price">{formatPrice(p.price)}</span>
        <span className={`chat-card-stock ${inStock.length ? '' : 'out'}`}>
          {inStock.length ? `In stock: ${inStock.join(', ')}` : 'Sold out'}
        </span>
      </div>
    </Link>
  )
}

// After-service survey on each answer: thumbs up, or thumbs down with a reason and optional note.
function FeedbackBar({ msg, onChange }: { msg: Message; onChange: (f: Feedback) => void }) {
  const [comment, setComment] = useState('')
  const [reason, setReason] = useState<'wrong' | 'unhelpful' | null>(null)
  if (!msg.replyId) return null
  const state = msg.feedback ?? 'none'

  if (state === 'sent') return <p className="chat-feedback-thanks">Thanks for the feedback!</p>

  if (state === 'down')
    return (
      <form
        className="chat-feedback-form"
        onSubmit={(e) => {
          e.preventDefault()
          sendFeedback({
            reply_id: msg.replyId!,
            helpful: false,
            accurate: reason === 'wrong' ? false : undefined,
            comment: comment.trim() || undefined,
          })
          onChange('sent')
        }}
      >
        <span>What went wrong?</span>
        <div className="chat-feedback-chips">
          <button type="button" className={reason === 'wrong' ? 'on' : ''} onClick={() => setReason('wrong')}>
            Info was wrong
          </button>
          <button type="button" className={reason === 'unhelpful' ? 'on' : ''} onClick={() => setReason('unhelpful')}>
            Not what I needed
          </button>
        </div>
        <input
          value={comment}
          maxLength={500}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Tell us what you needed (optional)"
        />
        <button type="submit" className="btn btn-primary btn-sm">
          Send feedback
        </button>
      </form>
    )

  return (
    <div className="chat-feedback">
      <span>Was this helpful?</span>
      <button
        aria-label="Helpful"
        onClick={() => {
          sendFeedback({ reply_id: msg.replyId!, helpful: true, accurate: true })
          onChange('sent')
        }}
      >
        👍
      </button>
      <button aria-label="Not helpful" onClick={() => onChange('down')}>
        👎
      </button>
    </div>
  )
}

// Floating chat window. Messages go to POST /api/chat, where the PydanticAI agent answers.
export default function ChatWidget() {
  const { user, loading: authLoading } = useAuth()
  const { results: pageResults, show: showOnPage, clear: clearPageResults } = useChatResults()
  const location = useLocation()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const openRef = useRef(open)
  openRef.current = open
  const [messages, setMessages] = useState<Message[]>(loadGuestChat)
  const prevUserId = useRef<number | null>(null)
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [step, setStep] = useState(0)
  const [unread, setUnread] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const launcherRef = useRef<HTMLButtonElement>(null)
  const askRef = useRef<(text: string) => void>(() => undefined)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, open, sending])

  // Opening the chat puts the cursor in the message box and clears the unread dot.
  useEffect(() => {
    if (open) {
      setUnread(false)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  // Cycle the progress text while waiting for the agent.
  useEffect(() => {
    if (!sending) return
    setStep(0)
    const t = setInterval(() => setStep((s) => Math.min(s + 1, PROGRESS_STEPS.length - 1)), 1300)
    return () => clearInterval(t)
  }, [sending])

  // Other parts of the site can open the chat, optionally with a question to ask right away
  // (e.g. "Ask about this item" on a product page, or the empty search state).
  useEffect(() => {
    const openChat = (e: Event) => {
      setOpen(true)
      const ask = (e as CustomEvent<{ ask?: string }>).detail?.ask
      if (ask) setTimeout(() => askRef.current(ask), 100)
    }
    window.addEventListener('open-chat', openChat)
    return () => window.removeEventListener('open-chat', openChat)
  }, [])

  // Logged-in shoppers: the saved conversation comes back from the database every time they log in.
  // Guests: the chat survives a refresh in this tab (sessionStorage) but is never stored on the server.
  useEffect(() => {
    if (authLoading) return
    if (!user) {
      // Logging out starts a fresh guest chat; a guest refreshing keeps theirs (loaded in useState above).
      if (prevUserId.current !== null) {
        prevUserId.current = null
        sessionStorage.removeItem(GUEST_KEY)
        setMessages([GREETING])
        clearPageResults() // a fresh chat starts with a clean page
      }
      return
    }
    prevUserId.current = user.id
    sessionStorage.removeItem(GUEST_KEY)
    fetchChatHistory().then((saved) => {
      const restored: Message[] = saved.map((m) => ({
        role: m.role,
        content: m.content,
        products: m.products,
        replyId: m.reply_id ?? undefined,
        feedback: m.reply_id ? 'sent' : undefined,
      }))
      setMessages([GREETING, ...restored])
    })
  }, [user, authLoading]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!authLoading && !user) sessionStorage.setItem(GUEST_KEY, JSON.stringify(messages.slice(-30)))
  }, [messages, user, authLoading])

  const updateMessage = (i: number, patch: Partial<Message>) =>
    setMessages((m) => m.map((msg, j) => (j === i ? { ...msg, ...patch } : msg)))

  async function ask(text: string) {
    const trimmed = text.trim()
    if (!trimmed || sending) return
    // Guests: send recent turns so the agent remembers the conversation. Logged-in: the server loads it.
    const history = messages
      .slice(1)
      .slice(-GUEST_HISTORY_TURNS)
      .map((m) => ({ role: m.role, content: m.content }))
    setMessages((m) => [...m, { role: 'user', content: trimmed }])
    setInput('')
    setSending(true)
    try {
      const page = currentPageContext(location.pathname, location.search, pageResults)
      const r = await sendChat(trimmed, user ? [] : history, page)
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          content: r.reply,
          products: r.products,
          suggestions: r.suggestions,
          navigate: r.navigate,
          replyId: r.reply_id,
          feedback: 'none',
        },
      ])
      // API contract: the agent's structured matches (r.products) are rendered on the page as product cards.
      // Skip it when the only match is the product already open on this page (it would just repeat the page).
      const onlyThisProduct =
        r.products.length === 1 && page.page_type === 'product' && r.products[0].product_id === page.product_id
      if (r.products.length > 0 && !onlyThisProduct) {
        showOnPage({
          title: r.results_title || 'Matching items',
          question: trimmed,
          products: r.products,
          owner: user ? `u${user.id}` : 'guest',
          query: r.results_query,
          total: r.results_total,
        })
      }
      const target = r.navigate ? pathFor(r.navigate) : null
      if (AUTO_NAVIGATE && target && target !== location.pathname + location.search) navigate(target)
      if (!openRef.current) setUnread(true)
    } catch (err) {
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          content: (err as Error).message || 'Sorry, I could not reach the store right now.',
          failed: trimmed,
        },
      ])
    } finally {
      setSending(false)
    }
  }
  askRef.current = ask

  // Resend a failed question: drop the failed attempt (question + error) and ask again.
  function retry(i: number) {
    const question = messages[i].failed
    if (!question) return
    setMessages((m) => m.filter((_, j) => j !== i && j !== i - 1))
    setTimeout(() => askRef.current(question), 0)
  }

  function send(e: FormEvent) {
    e.preventDefault()
    ask(input)
  }

  const last = messages[messages.length - 1]
  const hasAsked = messages.some((m) => m.role === 'user')
  const chips =
    last.role === 'assistant' && last.suggestions && last.suggestions.length > 0 && hasAsked
      ? last.suggestions
      : !hasAsked || !last.suggestions?.length
        ? pageStarters(location.pathname, location.search)
        : []

  return (
    <div className="chat-root">
      {open && (
        <section
          className="chat-panel"
          aria-label="Chat with Campus Customs"
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              setOpen(false)
              launcherRef.current?.focus()
            }
          }}
        >
          <header className="chat-header">
            <div className="chat-header-id">
              <span className="chat-header-avatar">
                <BulldogAvatar size={44} />
              </span>
              <div>
              <strong>Campus Customs Assistant</strong>
              <small>Live prices and stock from our inventory</small>
              </div>
            </div>
            <button className="chat-close" aria-label="Close chat" onClick={() => setOpen(false)}>
              ×
            </button>
          </header>
          <div className="chat-messages" role="log" aria-live="polite" aria-relevant="additions">
            {messages.map((m, i) => (
              <div key={i} className={`chat-row ${m.role}`}>
                {m.role === 'assistant' ? (
                  <div className="chat-bubble-wrap">
                    <span className="chat-avatar">
                      <BulldogAvatar size={30} />
                    </span>
                    <div className="chat-bubble assistant">
                      <ChatText text={m.content} />
                    </div>
                  </div>
                ) : (
                  <div className="chat-bubble user">
                    <ChatText text={m.content} />
                  </div>
                )}
                {m.products && m.products.length > 0 && (
                  <div className="chat-cards">
                    {m.products.map((p) => (
                      <ChatProductCard key={p.product_id} p={p} />
                    ))}
                  </div>
                )}
                {m.navigate && !AUTO_NAVIGATE && pathFor(m.navigate) && (
                  <Link to={pathFor(m.navigate)!} className="chat-goto">
                    Take me there →
                  </Link>
                )}
                {m.failed && (
                  <button className="chat-retry" onClick={() => retry(i)}>
                    ↻ Try again
                  </button>
                )}
                {m.role === 'assistant' && <FeedbackBar msg={m} onChange={(f) => updateMessage(i, { feedback: f })} />}
              </div>
            ))}
            {sending && (
              <div className="chat-bubble-wrap">
                <span className="chat-avatar thinking">
                  <BulldogAvatar size={30} />
                  <span className="thought" aria-hidden="true">
                    <i />
                    <i />
                    <i />
                  </span>
                </span>
                <div className="chat-bubble assistant typing working" aria-label={`Assistant is working: ${PROGRESS_STEPS[step]}`}>
                  {/* the mascot trots along a little track while the agent searches */}
                  <div className="run-track" aria-hidden="true">
                    <span className="runner">
                      <BulldogAvatar size={26} />
                    </span>
                    <span className="dust d1" />
                    <span className="dust d2" />
                  </div>
                  <span className="progress-text">{PROGRESS_STEPS[step]}</span>
                </div>
              </div>
            )}
            {!sending && last.role === 'assistant' && chips.length > 0 && (
              <div className="chat-suggestions">
                {chips.map((s) => (
                  <button key={s} onClick={() => ask(s)}>
                    {s}
                  </button>
                ))}
              </div>
            )}
            <div ref={endRef} />
          </div>
          <form className="chat-input" onSubmit={send}>
            <input
              ref={inputRef}
              value={input}
              maxLength={1000}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about hoodies, sizes, prices…"
              aria-label="Message"
            />
            <button type="submit" className="btn btn-primary btn-sm" disabled={!input.trim() || sending}>
              Send
            </button>
          </form>
        </section>
      )}
      <button
        ref={launcherRef}
        className="chat-launcher"
        aria-label={open ? 'Close chat' : unread ? 'Open chat (new reply)' : 'Open chat'}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        {open ? <span className="chat-launcher-x">×</span> : <BulldogAvatar size={52} className="launcher-dog" />}
        {unread && !open && <span className="chat-unread" aria-hidden="true" />}
      </button>
    </div>
  )
}
