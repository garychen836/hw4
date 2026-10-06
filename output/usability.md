# Campus Customs: Usability Improvements

This file lists the improvements we made to the **website (UI/UX)** and the **shopping agent**, what each one adds, and why it helps shoppers. Part 1 is the work done in Problem 9. Part 2 collects the improvements we made along the way in Problems 3-8. Each item was tested in the browser or against the live agent; results are noted where they matter.

---

## Part 1: Problem 9 improvements

### Summary (rubric: 2 front-end + 2 agent/backend)

| # | Type | Improvement | Where to see it in the running app |
|---|---|---|---|
| F1 | **Front-end** | Page-aware chat shortcuts: "Ask about this item" button + starter questions that match the page | Open any product page → "💬 Ask about this item" under "Add to bag"; open the chat on a product page to see its starter chips |
| F2 | **Front-end** | No dead ends while browsing: loading placeholders, a helpful "no results" state, and "See all N matches" from chat results | Products page → search "pink"; ask the chat "what hoodies do you have?" → "See all 27 matches →" |
| A1 | **Agent / backend** | New agent tool `find_similar`: similar in-stock items in the shopper's size | Product page → chat chip "Show me similar items", or "It's sold out in M, anything like this?" |
| A2 | **Agent / backend** | One smart search engine for the agent and the website (`GET /api/search`): plurals, synonyms, every-word matching, relevance order | Products page → search "hoodies" (27 results; was 0) or "navy quarter zip" (5 results; was 87 loose matches) |
| A3 | **Agent / backend** | Feedback loop: an automatic answer-checking loop before every reply, plus a 👍/👎 survey after every reply, both logged and linked | Ask the chat anything → "Was this helpful? 👍 👎" under the answer; 👎 opens "Info was wrong / Not what I needed" |

These are the featured ones; we built more than the minimum. **7 more Problem 9 improvements** (a bulldog mascot with a running and thinking animation, progress messages, "Try again", unread-reply dot, keyboard and screen-reader support, full-screen chat on phones, no duplicate results) follow below, and **Part 2** lists the **25+ improvements made along the way in Problems 3-8** (front-end and agent), each with what it adds and why it helps.

---

### F1 (front-end). Page-aware chat shortcuts

**What we added**
- An **"💬 Ask about this item"** button on every product page. One click opens the chat and asks *"Tell me about this one. Is it in stock in XS?"* using the size selected on the page.
- **Starter questions that match the page** when the chat opens: on a product page "Is this in stock in my size?", "Does it come in other colors?", "Show me similar items"; on a Products search for "hockey" "Help me choose from these hockey", "Cheapest hockey in stock", "Gifts under $40"; on Home, popular starting points. After an answer, the agent's own follow-up suggestions take over.

**Why it helps**
- *Shopper:* no typing or describing the product; the most common questions about the item in front of them are one tap away.
- *Business:* product pages turn into conversations at the moment of interest (size and stock questions are what decide a purchase), and the chips show off what the assistant can do without any help text.

**Tested:** On the Saybrook College Crewneck page (XS selected) the button sent the question automatically and the answer described the item and said "XS is in stock." The starter chips matched the page on product, Products, and Home.

### F2 (front-end). No dead ends while browsing

**What we added**
- **Loading placeholders:** shimmering placeholder cards while products load or a search runs, instead of a blank "Loading…".
- **Helpful empty state:** when nothing matches, "No products match 'pink'." with **Clear search and filters** and **Ask our assistant** (which opens the chat and asks "Do you have anything like 'pink'?").
- **"See all N matches →"** in the on-page chat results when the agent's search found more than the 6 cards it shows. It opens the Products page with that search, sorted by **Best match**, and the chat results collapse to a slim bar so nothing is shown twice.

**Why it helps**
- *Shopper:* the page never looks broken or empty without a next step, and they can go from the chat's top picks to the complete list in one click.
- *Business:* fewer abandoned searches; a "no results" moment becomes a chat that can suggest the closest products instead of losing the sale.

**Tested:** "pink" showed the empty state with both buttons; "what hoodies do you have?" showed "See all 27 matches →", which opened `/products?q=hoodies` with exactly 27 products and the chat results collapsed.

### A1 (agent / backend). New agent tool: `find_similar`

**What we added**
- A read-only tool in `backend/tools.py` (wired in `agent.py`, listed in the prompt's "Which tool to call" table). Given a product (or, by default, the product open on the shopper's page) and optionally a size, it returns up to 6 similar items that are **in stock** (in that size), ranked by: same kind of garment (hoodie, crewneck, quarter-zip, jacket, tee), same theme (residential college, sport, family, graduate school, bulldog), closest garment color, then closest price. It also tells the agent *how* the items are similar, so the reply describes them accurately.

**Why it helps**
- *Shopper:* "show me similar items" and "it's sold out in M, anything like this?" get relevant, available alternatives (other college crewnecks for a college crewneck, other sport hoodies in M for a sold-out hockey hoodie) instead of a vague keyword search.
- *Business:* a sold-out size becomes a sale of a similar item, and the answer takes **one tool call** (2 model calls) because the agent no longer has to guess search keywords.

**Tested (live agent):**

| Page and question | Answer |
|---|---|
| Saybrook College Crewneck, M: "Show me similar items" | 4 college crewnecks in M (Grace Hopper, Pierson, Davenport, Jonathan Edwards); 1 tool call |
| Ice Hockey Left Chest Hoodie (sold out in M): "anything like this in my size?" | "The Ice Hockey Left Chest Hoodie is sold out in M. These similar navy sport hoodies are available in M: Fencing, Sailing, Squash, and Volleyball Left Chest Hoodies." |

A first version let the agent call fencing and sailing hoodies "hockey-style"; adding the "similar by kind/theme; different designs" note to the tool result fixed it.

### A2 (agent / backend). One smart search engine for the agent and the website

**What we added**
- `GET /api/search?q=` in `backend/main.py` runs the **same catalogue search the agent uses** (`tools.search_products`): plurals ("hoodies" → hoodie), synonyms ("tee" → t-shirt, "family" → mom/dad/grandpa…, "college" → all residential colleges), and relevance ranking. A new `match_all` mode keeps items matching **every** word (falling back to any word when nothing matches all), which suits a browsing grid.
- The Products page search box now uses it (debounced 250 ms, out-of-date responses ignored) and defaults to **Sort: Best match**.
- The chat reply now carries `results_query` and `results_total`, counted with the same page search, so the "See all N matches" number always equals what the Products page shows.

**Why it helps**
- *Shopper:* typing "hoodies" in the search box used to find **0** products (no product text contains that exact word); now it finds **27**. "navy quarter zip" finds the **5** navy quarter-zips instead of 87 loose matches. The search box and the chat now agree.
- *Business:* better on-site search means more products found and fewer bounces; one search engine to maintain instead of two that disagree.

**Tested:** hoodies 27 (was 0), "gray tee" 17, family 12, hockey 5, "navy quarter zip" 5, saybrook 3, pink 0 with the empty state.

### A3 (agent / backend). Feedback loop: check every answer, and ask the shopper

*(Built in Problem 5 and refined in Problems 6-8; featured here because it is central to answer quality.)*

**What we added**
- **Automatic checking loop (before the shopper sees anything).** An output validator in `backend/agent.py` checks each answer against `campus_customs.db`: every product id and navigation target exists; every `$` price is the real price of a product the agent looked up; every stock count ("only 2 left") is a quantity a tool returned; and every price or stock claim was looked up in this turn. Products named in the reply automatically get their card. If a check fails, the agent gets the exact problem and the real numbers back and fixes its answer (up to 2 retries); if it still fails, the shopper gets a safe "I couldn't double-check that, so I'd rather not guess" instead of a wrong answer. A loop guard stops repeated identical tool calls.
- **Run log.** Every answer is saved in the `chat_runs` table: question, reply, products, each tool call with its arguments, any failed checks, status (`ok`, `fixed` after a retry, `canned` small talk, `fallback`, `error`), model, tokens (including cached), and time.
- **Customer survey (after every answer).** "Was this helpful? 👍 👎" under each reply. 👍 records helpful + accurate; 👎 asks **"Info was wrong"** or **"Not what I needed"** plus an optional "Tell us what you needed" note. Ratings go to `chat_feedback` with the reply's `reply_id`, so each one links to the exact run (and, for logged-in shoppers, to the saved message). Shoppers can only rate their own conversation.

**Why it helps**
- *Shopper:* wrong prices, invented stock counts, or made-up products are caught before they're shown; it's easy to say when an answer missed the mark.
- *Business:* trust (no promising stock we don't have), and a built-in way to find and fix problems. One query lists every thumbs-down with the question, answer, tool calls, and failed checks side by side:

```sql
SELECT r.message, r.reply, r.tool_calls, r.checks, r.status, f.accurate, f.comment
FROM chat_feedback f JOIN chat_runs r USING (reply_id) WHERE f.helpful = 0;
```

**Tested:** a unit test of the validator with deliberately bad answers (a made-up product id, $49.99 for a $68 hoodie, an invented "only 7 left", stock or price claims without a lookup, navigation to a fake product) triggered a retry with the exact problem every time, while correct answers and "under $40" budget phrases passed. In the browser, 👎 → "Not what I needed" + a note was saved and linked to its run. At the time of writing, `chat_runs` holds 139 runs (1 fixed by a retry, 1 safe fallback, 6 canned small-talk replies) and `chat_feedback` holds 3 ratings (2 👍, 1 👎).

---

### Additional Problem 9 improvements

### 0. A bulldog mascot for the assistant, with a "running and thinking" animation

**What:** An original kawaii bulldog mascot (hand-drawn SVG in `frontend/src/components/BulldogAvatar.tsx`) in a squishy-pillow style: one round golden body, a white face patch, small floppy ears, a big black nose, shiny eyes, rosy cheeks, a tiny underbite fang, stubby paws, and a navy belly with a white "Y". It appears on the floating chat button (with a gentle bob and an occasional blink; it wiggles on hover), in the chat header, next to every assistant reply, and in the home page "Not sure about size or color?" band. While the agent works, a mini bulldog **trots along a little track** kicking up dust, and the avatar shows a **thought cloud** with pulsing dots above the progress text ("Searching the catalogue…"). All motion is turned off for shoppers who prefer reduced motion.

**Why it helps:** It gives the assistant a friendly, on-brand personality (the Bulldogs), makes the chat button easy to spot, and the running and thinking animation makes the 3-5 second wait feel playful and clearly "in progress". We drew our own character in a general bulldog style rather than copying Yale's official logos or mascot artwork, which are trademarks. It took three rounds of feedback: the first drafts read as a cat and then a tiger, so the final design uses the rounder, simpler pillow style.

### 1. Progress messages while the agent works

**What:** Instead of a single "Checking our inventory…", the waiting bubble shows animated dots and steps through "Reading your question… → Searching the catalogue… → Checking sizes and stock… → Double-checking prices…".

**Why it helps:** Answers take about 3-5 seconds. Visible progress makes the wait feel shorter and explains why it takes a moment (the assistant is checking real stock and prices, not guessing).

### 2. "Try again" when a message fails

**What:** If the server or AI gateway is unreachable, the error bubble gets a **↻ Try again** button that resends the same question (without duplicating it in the chat).

**Why it helps:** Shoppers don't have to retype, and a temporary network issue doesn't end the conversation. Tested by forcing one failure: the retry returned a normal answer and the question appeared only once.

### 3. Unread-reply dot on the chat button

**What:** If a reply arrives while the chat is closed, a red dot appears on the 💬 button and its screen-reader label becomes "Open chat (new reply)". Opening the chat clears it.

**Why it helps:** Shoppers who close the chat to look at the page don't miss the answer.

### 4. Keyboard and screen-reader accessibility

**What:**
- Opening the chat puts the cursor in the message box; **Esc** closes it and returns focus to the chat button.
- The message list is an `aria-live` log, so screen readers announce new replies.
- The chat button reports open/closed (`aria-expanded`); category chips report which is selected (`aria-pressed`); the product count is announced when a search updates.
- A clear blue focus outline appears on every link, button, and input when using the keyboard.

**Why it helps:** Keyboard-only and screen-reader shoppers can use the whole store and the assistant, and everyone gets faster keyboard use (type, Enter, Esc).

### 5. Full-screen chat on phones

**What:** On screens narrower than 560 px the chat opens as a full-screen sheet; the floating button hides while it's open, and the message box uses a 16 px font (so iPhones don't zoom in when you tap it).

**Why it helps:** The floating panel was cramped on a phone. Full screen gives room for replies and product cards. Tested at 375×812.

### 6. No duplicate results on a product page

**What:** If the only match is the product already open (for example, "Tell me about this one"), the chat answers without also putting that same product in the on-page results section.

**Why it helps:** It removes a redundant block that pushed the product details down the page.

---

## Part 2: Improvements made along the way (Problems 3-8)

### Website (UI/UX)

| Improvement | What it adds | Why it helps |
|---|---|---|
| Yale-style design (P3) | Open Sans / Nunito Sans, Yale navy, black buttons, light-gray sections, announcement bar, footer with the store address | Feels familiar and trustworthy to people who know the official bookstore site |
| Responsive nav (P3) | Nav bar with Home, Products, About Us, Log in, Create account; a hamburger menu on phones | Every main page is one tap away on any screen |
| Product photo cleanup (P3, P6, P8) | Cut-out photos moved from black backgrounds with jagged edges to a soft light-gray background; very rough ones are smoothed or use the original | Cleaner, consistent product grid; no distracting halos or white slivers |
| Product cards with short descriptions (P3) | Photo, name, type, two-line description, price, "Sold out" badge | Shoppers can compare at a glance without opening every item |
| Amazon-style product page (P3) | Large photo on one side; price, stock status, size picker ("Only 2 left", sold-out sizes crossed out), specs, and description on the other | All buying information in one view; honest stock per size |
| Category chips, search, sort (P3) | Filter by Hoodies / Crewnecks / Quarter-Zips / Jackets / Tees, keyword search, sort by price | Fast narrowing of 102 products |
| Vivid home page (P3) | Full-width Yale-blue hero with a floating product collage, a scrolling ticker, shop-by-collection tiles, a Yale-vs-Harvard feature, category circles, best sellers, and an assistant call-out | Clear entry points (by collection, category, or chat) and a confident first impression |
| Collections (P3) | Residential Colleges, Varsity Sports, Yale Family, Graduate & Professional, Classic Yale; `/products?collection=…` | Matches how shoppers think ("something for my dad", "my college") |
| Account flow (P4) | Sign up with first/last name, email, password plus confirmation; clear inline errors; nav shows "Hi, *name*" and Log out; the session survives refresh | Simple, familiar account steps with helpful messages |
| On-page chat results (P7) | The agent's matches appear as product cards on the current page, slide in, can be hidden or cleared, survive a refresh, and collapse on product pages | Shoppers see results where they're browsing, not only in a small chat window |
| Results only for this conversation (P8) | Results record whose chat asked for them and are cleared when the chat resets; hidden on Log in and Create account | No confusing leftover results from a previous visitor or session |
| Safe chat formatting (P5) | Bold text and bullet lists render properly; no raw `**` or `-` | Readable answers, with no HTML injection risk |

### Agent

| Improvement | What it adds | Why it helps |
|---|---|---|
| Answers grounded in the database (P5-P6) | Read-only tools for search, product details, and stock by size; the prompt says facts only come from tools | Real prices and stock, not guesses |
| Sanity-check loop (P5-P6) | Before a reply is shown, code checks product ids, every `$` price, every stock count ("only 2 left"), and that claims were looked up; failures go back to the agent (2 retries), then a safe fallback | Hallucinated prices and quantities are caught before shoppers see them |
| Honest stock language (P6) | Every size has a status: in stock, low stock ("only N left"), sold out, or unclear; "unclear" when the database can't confirm | Clear, trustworthy availability answers |
| Garment color vs print color (P5) | `main_color` separates "a gray hoodie with a navy logo" from "a navy hoodie" | Fixed a real mistake where a gray hoodie was called navy |
| Sold-out matches aren't hidden (P5) | When a size filter hides the best match, search reports it, so the agent says "The navy Ice Hockey hoodie is sold out in M" and offers alternatives | Shoppers learn the truth instead of seeing a silently worse match |
| Product cards in chat (P7) | Every product the reply names gets a card (code adds any the agent forgot) | Photos, prices, and sizes without long text |
| Optional navigation (P5, P7) | "Take me to the Yale vs Harvard shirt" opens that page; ordinary questions don't yank the shopper away | Helpful when asked, never disruptive |
| Suggestions (P5) | Up to 3 tap-able follow-up questions after each answer | Keeps the conversation moving with one tap |
| After-service survey (P5) | 👍 / 👎 under every answer; 👎 asks "Info was wrong" or "Not what I needed" plus a note; saved with the run log | Shoppers can flag problems, and the team can trace each rating to the exact tool calls |
| Memory and identity (P8) | Logged-in history is saved and reloaded on every login; the agent knows the shopper's name and email; guests can chat but nothing is stored | Personal, continuous service; privacy for guests |
| Page awareness (P8) | The website sends the open product, selected size, filters, and on-page results; "this one", "in pink", "a bigger size", and "the second one" are resolved correctly | Shoppers can talk naturally about what they're looking at |
| Safety (P5) | Stays on topic; refuses prompt-injection and fake discounts; redacts card numbers and SSNs before logging or sending to the AI; rate limits; read-only tools | Safe for shoppers and the store |
| Speed and cost (P5-P6) | Cheapest model with reasoning off, short tool results, short memory, hard caps, near-miss product ids resolved automatically, loop guard, free replies to small talk; about 88% of input tokens served from the prompt cache | About 2 model calls and 3-4 s per answer; greetings are instant and free |
| Reliability fixes (P8) | Repeat-call loop guard; `bigger_sizes` for "a bigger size"; guest chat kept after refresh | Fewer stalls and wrong answers in real conversations |

---

## How we tested Problem 9

| Check | Result |
|---|---|
| Product page starters | "Is this in stock in my size?", "Does it come in other colors?", "Show me similar items" |
| "Ask about this item" (Saybrook crewneck, XS selected) | Sent automatically; answer described the item and said "XS is in stock" |
| Progress text | All four steps shown during one answer |
| "See all 27 matches" after "what hoodies do you have?" | Opened `/products?q=hoodies`: "27 products for 'hoodies'", sorted by Best match, chat results collapsed |
| Products search | "hoodies" 27 (was 0), "navy quarter zip" 5, "family" 12, "pink" 0 with the empty state |
| `find_similar` (Saybrook crewneck, M; Ice Hockey hoodie sold out in M) | 4 college crewnecks in M; 4 navy sport hoodies in M, described accurately; 1 tool call each |
| Esc in chat | Closed the chat; focus returned to the chat button |
| Forced network failure | Error bubble with "Try again"; retry answered; the question appeared once |
| Reply while the chat is closed | Red dot on the chat button; label "Open chat (new reply)" |
| Phone (375×812) | Chat fills the screen; launcher hidden; 16 px input |
