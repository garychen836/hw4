"""Campus Customs shopping agent (PydanticAI).

Wiring:
- System prompt: backend/prompts/prompt.md (+ a short per-request note: who is chatting and what page they're on).
- Deps (per message): the logged-in shopper's profile (or guest) and the page context the website sent.
- Model: OpenAI through the Portkey gateway, key from .env (PORTKEY_API_KEY); MODEL_NAME picks the model.
- Tools: read-only catalogue tools from backend/tools.py.
- Output: models.AgentReply (reply text, product_ids, optional navigate, suggestions).

Internal sanity-check loop (output validator): before the shopper sees a reply, code checks that every
product_id and navigation target exists, every $ price in the text is a real catalogue price for a product
the agent looked up or showed, every stock count ("only 3 left") is a quantity a tool returned, and that
price / stock claims were backed by a tool call in this run.
If a check fails, the agent gets a ModelRetry with the exact problem and fixes its answer (max 2 retries).
If it still fails, the shopper gets a safe fallback reply. Every run is logged to the chat_runs table.
"""

import fcntl
import json
import os
import re
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel
from pydantic_ai import Agent, ModelRetry, RunContext, capture_run_messages
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

import tools
from models import (
    AgentReply,
    AuditEntry,
    AuditEvent,
    ChatHistoryResult,
    ChatTurn,
    ChatUsage,
    PageContext,
    PageView,
    ProductDetails,
    SearchResult,
    ShopperProfile,
    StockCheck,
    ToolError,
)

BACKEND = Path(__file__).resolve().parent
ROOT = BACKEND.parent
PROMPT_PATH = BACKEND / "prompts" / "prompt.md"
AUDIT_PATH = ROOT / "output" / "audit_trail.json"  # append-only; never wiped between runs

load_dotenv(ROOT / ".env")
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

MODEL_NAME = os.getenv("MODEL_NAME", "gpt-6-luna")  # cheapest tier; set MODEL_NAME in .env to change
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1")

# Cost and runaway guards for one shopper message.
MAX_HISTORY_TURNS = 8  # only the most recent turns are sent to the model
MAX_TURN_CHARS = 600  # long old messages are trimmed before resending
USAGE_LIMITS = UsageLimits(request_limit=6, tool_calls_limit=8, total_tokens_limit=40_000)
# Luna models only allow function tools with reasoning off; it is also the cheapest and fastest setting.
REASONING_EFFORT = os.getenv("REASONING_EFFORT", "none")
MODEL_SETTINGS = OpenAIChatModelSettings(
    max_tokens=700, parallel_tool_calls=True, openai_reasoning_effort=REASONING_EFFORT
)
READ_ONLY_TOOLS = {
    "search_products", "get_product", "check_stock", "find_similar", "get_my_profile", "get_chat_history", "get_current_page",
}
MAX_CARDS = 6

PRICE_RE = re.compile(r"\$\s?(\d+(?:\.\d{1,2})?)")
# "only 3 left", "3 left in M", "12 in stock", "3 available", "3 remaining", "3 units"
COUNT_RE = re.compile(r"\b(\d{1,4})\s+(?:left|in stock|available|remaining|units?|pieces?)\b", re.I)
COUNT_RE2 = re.compile(r"\bonly\s+(\d{1,4})\b", re.I)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Basic profanity / insult list for the reply check (shopper messages are not blocked, only the agent's replies).
ABUSIVE_RE = re.compile(
    r"\b(fuck\w*|shit\w*|bitch\w*|bastard|asshole|dick|crap|damn|idiot\w*|stupid|moron\w*|dumb|loser|shut up|hate you)\b",
    re.I,
)
STOCK_WORDS = re.compile(r"\b(in stock|sold out|out of stock|left in|available in|only \d+ left)\b", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _short(d: dict) -> dict:
    """Shorten long argument values for the audit trail."""
    return {k: (v[:80] + "…" if isinstance(v, str) and len(v) > 80 else v) for k, v in d.items() if v not in (None, "")}


# ---------- model ----------


def get_model() -> OpenAIChatModel:
    key = os.environ.get("PORTKEY_API_KEY")
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is not set in .env")
    client = AsyncOpenAI(
        api_key=key,
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-api-key": key, "x-portkey-provider": "openai"},
        timeout=45,
        max_retries=1,
    )
    return OpenAIChatModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


# ---------- per-run state ----------


@dataclass
class Deps:
    profile: ShopperProfile | None = None  # None = guest
    page: PageContext | None = None  # what the shopper is looking at
    # Filled by tools during the run; used by the sanity checks.
    seen: dict[str, float] = field(default_factory=dict)  # product_id -> price, for every product a tool returned
    counts: set[int] = field(default_factory=set)  # every exact stock quantity a tool returned this turn
    names: dict[str, str] = field(default_factory=dict)  # product_id -> name, for attaching forgotten cards
    page_product_name: str | None = None  # name of the product open on the page (for the short instruction)
    called: set[str] = field(default_factory=set)  # tool+args already called this turn (loop guard)
    last_search: tuple[str, int] | None = None  # (query, total matches) of the last catalogue search, for "See all"
    tool_log: list[dict] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)  # problems found by the validator (kept for the log)
    card_fixes: list[str] = field(default_factory=list)  # cards code attached that the agent left out
    memo: dict[str, BaseModel] = field(default_factory=dict)  # identical lookups in one turn hit the database once
    events: list[dict] = field(default_factory=list)  # timestamped steps for the audit trail
    t0: float = field(default_factory=time.perf_counter)
    wall0: float = field(default_factory=time.time)  # same moment as t0, as a Unix timestamp

    def event(self, type_: str, name: str | None = None, args: dict | None = None, result: str | None = None) -> None:
        self.events.append(
            {"t": _now(), "ms": int((time.perf_counter() - self.t0) * 1000), "type": type_, "name": name,
             "args": _short(args) if args else None, "result": (result or "")[:200] or None}
        )

    def lookup(self, name: str, args: dict, fn) -> BaseModel:
        key = f"{name}:{json.dumps(args, sort_keys=True)}"
        if key not in self.memo:
            self.memo[key] = fn(**args)
        return self.memo[key]

    def note(self, result: BaseModel) -> None:
        """Remember the prices and stock counts the database actually returned."""
        if isinstance(result, SearchResult):
            for r in result.results:
                self.seen[r.product_id] = r.price
                self.names[r.product_id] = r.name
            for r in result.sold_out_in_size:
                self.seen[r.product_id] = r.price
                self.names[r.product_id] = r.name
        elif isinstance(result, ProductDetails):
            self.seen[result.product_id] = result.price
            self.names[result.product_id] = result.name
            self.counts |= {s.quantity for s in result.sizes if s.quantity is not None}
            self.counts.add(result.total_in_stock)
        elif isinstance(result, StockCheck):
            self.seen[result.product_id] = result.price
            self.names[result.product_id] = result.name
            if result.quantity is not None:
                self.counts.add(result.quantity)


agent = Agent(
    get_model(),
    deps_type=Deps,
    output_type=AgentReply,
    instructions=PROMPT_PATH.read_text(),
    model_settings=MODEL_SETTINGS,
    retries=2,
)


@agent.instructions
def shopper_context(ctx: RunContext[Deps]) -> str:
    """Short per-message note (kept small; details come from get_my_profile / get_current_page)."""
    p, page = ctx.deps.profile, ctx.deps.page
    parts = [
        f"Shopper: logged in as {p.name} (first name {p.first_name or p.name}; email {p.email}; username {p.username}; "
        f"member since {p.member_since[:10]})."
        if p
        else "Shopper: guest (not logged in); no profile or saved history."
    ]
    if page:
        where = f"Page: {page.page_type} ({page.path})"
        if page.product_id:
            name = ctx.deps.page_product_name or page.product_id
            where += f"; viewing product {name} [{page.product_id}]"
            if page.selected_size:
                where += f", size {page.selected_size} selected"
        if page.results_product_ids:
            where += f"; {len(page.results_product_ids)} chat results shown on the page ({page.results_title or 'untitled'})"
        if page.search or page.category or page.collection:
            where += f"; filters: {', '.join(x for x in (page.search, page.category, page.collection) if x)}"
        parts.append(where + ". Words like 'this one', 'it', 'these' refer to what's on this page; call get_current_page for details.")
    return " ".join(parts)


# ---------- tools (read-only) ----------


def _repeat(ctx: RunContext[Deps], name: str, args: dict) -> ToolError | None:
    """Loop guard: the same tool with the same arguments twice in one turn returns a nudge instead."""
    key = f"{name}:{json.dumps(args, sort_keys=True)}"
    if key in ctx.deps.called:
        ctx.deps.checks.append(f"repeat call blocked: {name}")
        ctx.deps.event("repeat_blocked", name, args)
        return ToolError(error=f"You already called {name} with these arguments in this turn. Use that result and answer now.")
    ctx.deps.called.add(key)
    return None


def _log(ctx: RunContext[Deps], name: str, args: dict, result: BaseModel) -> None:
    if isinstance(result, ToolError):
        summary = result.error
    elif isinstance(result, SearchResult):
        summary = f"{result.total_matches} matches"
    elif isinstance(result, StockCheck):
        summary = f"{result.product_id} {result.size}: {result.quantity} ({result.status})"
    elif isinstance(result, ChatHistoryResult):
        summary = f"{len(result.messages)} of {result.total_messages} past messages" if result.logged_in else "guest"
    elif isinstance(result, PageView):
        summary = f"{result.page_type}: {result.viewing.product_id if result.viewing else result.path}"
    elif isinstance(result, ShopperProfile):
        summary = f"user {result.user_id}"
    else:
        summary = getattr(result, "product_id", "")
    ctx.deps.tool_log.append({"tool": name, "args": args, "result": summary})
    ctx.deps.event("tool_call", name, args, str(summary))


@agent.tool
def search_products(
    ctx: RunContext[Deps],
    query: str = "",
    max_price: float | None = None,
    size_in_stock: str | None = None,
    limit: int = 6,
) -> SearchResult | ToolError:
    """Search the catalogue by keywords such as garment type, color, sport, college, school, or family member.

    Args:
        query: keywords, e.g. "navy hockey hoodie", "Saybrook", "dad crewneck". Empty returns everything.
        max_price: only items at or under this price in USD.
        size_in_stock: only items with this size available (XS, S, M, L, XL, XXL).
        limit: number of results to return (1-10, default 6).

    Returns price, main_color, colors, and in_stock_sizes for each match (no exact counts).
    """
    limit = max(1, min(limit, 10))  # the agent sees at most 10 results (cheap); the Products page can ask for more
    args = {"query": query, "max_price": max_price, "size_in_stock": size_in_stock, "limit": limit}
    if blocked := _repeat(ctx, "search_products", args):
        return blocked
    result = ctx.deps.lookup("search_products", args, tools.search_products)
    ctx.deps.note(result)
    if isinstance(result, SearchResult) and query.strip() and not max_price and not size_in_stock:
        ctx.deps.last_search = (query.strip(), result.total_matches)
    _log(ctx, "search_products", args, result)
    return result


@agent.tool
def get_product(ctx: RunContext[Deps], product_id: str) -> ProductDetails | ToolError:
    """Full details for one product: description, price, colors, and the exact stock count and status for every size.

    Use for "tell me about…", "what does it look like?", "what sizes / how many do you have?".
    """
    if blocked := _repeat(ctx, "get_product", {"product_id": product_id}):
        return blocked
    result = ctx.deps.lookup("get_product", {"product_id": product_id}, tools.get_product)
    ctx.deps.note(result)
    _log(ctx, "get_product", {"product_id": product_id}, result)
    return result


@agent.tool
def check_stock(ctx: RunContext[Deps], product_id: str, size: str) -> StockCheck | ToolError:
    """Exact stock count and status for one product in one size (XS, S, M, L, XL, XXL).

    Use for "is it in stock in M?" or "how many are left in L?".
    """
    if blocked := _repeat(ctx, "check_stock", {"product_id": product_id, "size": size}):
        return blocked
    result = ctx.deps.lookup("check_stock", {"product_id": product_id, "size": size}, tools.check_stock)
    ctx.deps.note(result)
    _log(ctx, "check_stock", {"product_id": product_id, "size": size}, result)
    return result


@agent.tool
def find_similar(
    ctx: RunContext[Deps], product_id: str = "", size_in_stock: str | None = None, limit: int = 4
) -> SearchResult | ToolError:
    """Items similar to one product (same kind of garment and/or same theme such as a college, sport, family,
    or school; closest color), in stock, best first. Use for "show me similar items", "something like this",
    or alternatives when an item is sold out in the shopper's size.

    Args:
        product_id: the product to match; leave empty to use the product open on the shopper's page.
        size_in_stock: only items with this size available (XS-XXL).
        limit: 1-6 (default 4).
    """
    pid = product_id or (ctx.deps.page.product_id if ctx.deps.page and ctx.deps.page.product_id else "")
    if not pid:
        return ToolError(error="No product given and none is open on the page. Ask which item they mean.")
    args = {"product_id": pid, "size_in_stock": size_in_stock, "limit": limit}
    if blocked := _repeat(ctx, "find_similar", args):
        return blocked
    result = ctx.deps.lookup("find_similar", args, tools.find_similar)
    ctx.deps.note(result)
    _log(ctx, "find_similar", args, result)
    return result


@agent.tool
def get_my_profile(ctx: RunContext[Deps]) -> ShopperProfile | ToolError:
    """The logged-in shopper's own profile: name, first/last name, email, username, member since.

    The same details are already in your instructions; this tool is a fallback. Guests have no profile.
    """
    if blocked := _repeat(ctx, "get_my_profile", {}):
        return blocked
    _log(ctx, "get_my_profile", {}, ctx.deps.profile or ToolError(error="guest"))
    if ctx.deps.profile is None:
        return ToolError(error="The shopper is a guest (not logged in), so there is no profile.")
    return ctx.deps.profile


@agent.tool
def get_chat_history(ctx: RunContext[Deps], query: str = "", limit: int = 10) -> ChatHistoryResult | ToolError:
    """The shopper's own earlier chat messages saved in the database (oldest first).

    The most recent turns are already in the conversation; use this for older ones ("what did I ask about last
    time?", "that hoodie you showed me yesterday"). `query` keeps only messages containing that text.
    """
    if blocked := _repeat(ctx, "get_chat_history", {"query": query, "limit": limit}):
        return blocked
    user_id = ctx.deps.profile.user_id if ctx.deps.profile else None
    result = tools.chat_history(user_id, query, limit)
    _log(ctx, "get_chat_history", {"query": query, "limit": limit}, result)
    return result


@agent.tool
def get_current_page(ctx: RunContext[Deps]) -> PageView | ToolError:
    """What the shopper is looking at right now: the product open on the page (full details and stock by size),
    the size they selected, Products-page filters, and the chat results shown on the page.

    Use to resolve "this one", "it", "these", "a different size", "in pink".
    """
    if blocked := _repeat(ctx, "get_current_page", {}):
        return blocked
    result = tools.current_page(ctx.deps.page)
    if result.viewing:
        ctx.deps.note(result.viewing)
    for r in result.results_on_page:
        ctx.deps.seen[r.product_id] = r.price
        ctx.deps.names[r.product_id] = r.name
    _log(ctx, "get_current_page", {}, result)
    return result


# ---------- internal sanity-check loop ----------


@agent.output_validator
def sanity_check(ctx: RunContext[Deps], out: AgentReply) -> AgentReply:
    problems: list[str] = []
    out.reply = out.reply.strip()
    if not out.reply:
        problems.append("The reply text is empty.")

    # 1. Every product id (cards and navigation) must exist in the catalogue.
    wanted = list(dict.fromkeys(out.product_ids))
    if out.navigate and out.navigate.type == "product":
        if not out.navigate.product_id:
            problems.append("navigate.type is 'product' but navigate.product_id is empty.")
        else:
            wanted.append(out.navigate.product_id)
    known = {c.product_id: c.price for c in tools.product_cards(wanted)} if wanted else {}
    missing = [pid for pid in wanted if pid not in known]
    if missing:
        problems.append(
            f"These product_ids do not exist: {missing}. Use only ids copied exactly from search_products results."
        )
    if out.navigate and out.navigate.type == "products" and not (out.navigate.search or out.navigate.collection):
        problems.append("navigate.type is 'products' but neither navigate.search nor navigate.collection is set.")

    # 2. Every $ price in the text must be the real price of a product the agent looked up or is showing.
    real_prices = set(ctx.deps.seen.values()) | set(known.values())
    quoted = {float(p) for p in PRICE_RE.findall(out.reply)}
    if quoted and not ctx.deps.seen:
        problems.append(
            "The reply states a price but no tool returned a price in this turn. Look the product up first, "
            "or say the price is unclear if the product isn't in the catalogue."
        )
    else:
        wrong = sorted(p for p in quoted if p not in real_prices)
        # Budget phrases like "under $40" aren't product prices; only flag amounts that look like a price claim.
        wrong = [p for p in wrong if not re.search(rf"(under|below|less than|up to|budget of)\s+\$\s?{p:g}", out.reply, re.I)]
        if wrong:
            problems.append(
                f"These prices are not catalogue prices for the products you looked up: {wrong}. "
                f"Real prices: {sorted(real_prices)}. Quote exact prices from tool results."
            )

    # 3. Stock claims need a tool call in this turn (stock changes; never answer from memory).
    if STOCK_WORDS.search(out.reply) and not ctx.deps.tool_log:
        problems.append("The reply makes a stock claim without checking. Call get_product or check_stock first.")

    # 4. Every stock count in the text ("only 3 left", "12 in stock") must be a quantity a tool returned.
    claimed = {int(n) for n in COUNT_RE.findall(out.reply) if n}
    claimed |= {int(n) for n in COUNT_RE2.findall(out.reply) if n}
    invented = sorted(claimed - ctx.deps.counts)
    if invented:
        problems.append(
            f"These stock counts were not returned by any tool: {invented}. Call get_product or check_stock for "
            "exact counts, or don't state a number (say 'in stock' / 'sold out' / 'unclear')."
        )

    # 6. Safety: no other people's data, no card/ID numbers, no abusive language in what the shopper sees.
    own_email = (ctx.deps.profile.email.lower() if ctx.deps.profile else None)
    leaked = [e for e in EMAIL_RE.findall(out.reply) if e.lower() != own_email]
    if leaked:
        problems.append("Never include other people's email addresses (or any email that isn't the shopper's own). Remove them.")
    if tools.redact(out.reply) != out.reply:
        problems.append("Never include card numbers or ID numbers in a reply. Remove them.")
    if ABUSIVE_RE.search(out.reply):
        problems.append("Your reply contains offensive or abusive language. Rewrite it politely and respectfully.")

    # 5. Cards: every product the reply names (that a tool returned this turn) gets a card, even if the
    #    agent forgot to list it. Fixed in code, no retry needed. Named products go first, in reply order.
    text = out.reply.lower()
    named = sorted(
        (pid for pid, name in ctx.deps.names.items() if name.lower() in text),
        key=lambda pid: text.index(ctx.deps.names[pid].lower()),
    )
    added = [pid for pid in named if pid not in out.product_ids]
    if added:
        out.product_ids = (named + [pid for pid in out.product_ids if pid not in named])[:MAX_CARDS]
        ctx.deps.card_fixes.extend(added)

    # 4. Keep the output tidy for the widget.
    out.suggestions = [s.strip()[:60] for s in out.suggestions if s.strip()][:3]

    if problems:
        ctx.deps.checks.extend(problems)
        ctx.deps.event("check_failed", "sanity_check", None, " ".join(problems))
        raise ModelRetry("Please fix your answer: " + " ".join(problems))
    return out


# ---------- history ----------


def build_history(turns: list[ChatTurn]) -> list[ModelMessage]:
    """Recent conversation as plain text turns (no old tool calls, to keep each request small)."""
    history: list[ModelMessage] = []
    for t in turns[-MAX_HISTORY_TURNS:]:
        text = t.content if len(t.content) <= MAX_TURN_CHARS else t.content[:MAX_TURN_CHARS] + "…"
        if t.role == "user":
            history.append(ModelRequest(parts=[UserPromptPart(content=text)]))
        else:
            history.append(ModelResponse(parts=[TextPart(content=text)]))
    return history


# ---------- run log (for "what went wrong?") ----------

RUN_LOG_SQL = """
CREATE TABLE IF NOT EXISTS chat_runs (
    reply_id TEXT PRIMARY KEY,
    user_id INTEGER,
    message TEXT NOT NULL,
    reply TEXT NOT NULL,
    product_ids TEXT,
    navigate TEXT,
    tool_calls TEXT,
    checks TEXT,
    status TEXT NOT NULL,          -- ok | fixed (passed after a retry) | canned (small talk, no model) | fallback | error
    model TEXT,
    requests INTEGER, input_tokens INTEGER, output_tokens INTEGER, cached_input_tokens INTEGER, duration_ms INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS chat_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reply_id TEXT NOT NULL,
    user_id INTEGER,
    helpful INTEGER,
    accurate INTEGER,
    comment TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def init_run_log() -> None:
    with sqlite3.connect(tools.DB_PATH) as conn:
        conn.executescript(RUN_LOG_SQL)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(chat_runs)")}
        if "cached_input_tokens" not in cols:  # added after the table was first created
            conn.execute("ALTER TABLE chat_runs ADD COLUMN cached_input_tokens INTEGER")


def log_run(row: dict) -> None:
    with sqlite3.connect(tools.DB_PATH) as conn:
        conn.execute(
            """INSERT INTO chat_runs (reply_id, user_id, message, reply, product_ids, navigate, tool_calls, checks,
                   status, model, requests, input_tokens, output_tokens, cached_input_tokens, duration_ms)
               VALUES (:reply_id, :user_id, :message, :reply, :product_ids, :navigate, :tool_calls, :checks,
                   :status, :model, :requests, :input_tokens, :output_tokens, :cached_input_tokens, :duration_ms)""",
            row,
        )


# ---------- entry point used by main.py ----------

class _Done(Exception):
    """Internal: skip the model (small talk)."""


FALLBACK_REPLY = (
    "Sorry, I couldn't double-check that answer, so I'd rather not guess. "
    "Could you rephrase, or browse the Products page in the meantime?"
)
BUSY_REPLY = "Sorry, I'm having trouble reaching our assistant right now. Please try again in a moment."


# Small talk that needs no product data is answered without a model call (free and instant).
SMALL_TALK = [
    (re.compile(r"^(hi|hello|hey|hiya|howdy|good (morning|afternoon|evening))( there)?[!. ]*$", re.I),
     "Hi! What Yale gear can I help you find today?", ["Navy hoodies in M", "Gifts under $40", "Yale vs Harvard tee"]),
    (re.compile(r"^(thanks|thank you|thx|ty|great,? thanks|perfect,? thanks|awesome,? thanks)( so much| a lot)?[!. ]*$", re.I),
     "You're welcome! Let me know if there's anything else I can help you find.", []),
    (re.compile(r"^(bye|goodbye|see you|that'?s all)[!. ]*$", re.I),
     "Thanks for stopping by Campus Customs. Boola boola!", []),
]


def small_talk(message: str) -> AgentReply | None:
    for pattern, reply, suggestions in SMALL_TALK:
        if pattern.match(message.strip()):
            return AgentReply(reply=reply, suggestions=suggestions)
    return None


async def answer(
    message: str,
    history: list[ChatTurn],
    profile: ShopperProfile | None = None,
    page: PageContext | None = None,
    deps_out: list | None = None,
) -> tuple[AgentReply, ChatUsage, str, list[str]]:
    """Run the agent for one shopper message. Returns (reply, usage, reply_id, checks).

    If deps_out is a list, the run's Deps is appended to it (main.py reads last_search for "See all").
    """
    deps = Deps(profile=profile, page=page)
    if deps_out is not None:
        deps_out.append(deps)
    if page and page.product_id:
        viewed = tools.get_product(page.product_id)
        deps.page_product_name = viewed.name if isinstance(viewed, ProductDetails) else None
    user_id = profile.user_id if profile else None
    reply_id = uuid.uuid4().hex
    started = time.perf_counter()
    usage = None
    status = "ok"
    canned = small_talk(message)
    started_at = _now()
    deps.t0, deps.wall0 = started, time.time()
    stop_reason = "final_answer"
    messages: list[ModelMessage] = []
    try:
        if canned:
            out, status, stop_reason = canned, "canned", "small_talk"
            deps.event("small_talk", "canned reply (no model call)")
            raise _Done
        past = build_history(history)
        with capture_run_messages() as messages:
            result = await agent.run(message, deps=deps, message_history=past, usage_limits=USAGE_LIMITS)
        messages = messages[len(past):]  # only this run's steps, not the replayed conversation
        out = result.output
        usage = result.usage
        if deps.checks:
            status, stop_reason = "fixed", "final_answer_after_fix"
        # Defense in depth: the agent may only have read-only tools.
        called = {p.tool_name for m in result.all_messages() for p in getattr(m, "parts", []) if isinstance(p, ToolCallPart)}
        assert called <= READ_ONLY_TOOLS | {"final_result"}, f"unexpected tool calls: {called}"
    except _Done:
        pass
    except (UnexpectedModelBehavior, UsageLimitExceeded) as e:
        status = "fallback"
        stop_reason = "fallback_usage_limit" if isinstance(e, UsageLimitExceeded) else "fallback_check_failed"
        deps.checks.append(f"{type(e).__name__}: {e}")
        deps.event("error", type(e).__name__, None, str(e))
        out = AgentReply(reply=FALLBACK_REPLY, suggestions=["Show me hoodies", "Gifts under $40"])
    except Exception as e:  # network / gateway problems
        status, stop_reason = "error", "error"
        deps.checks.append(f"{type(e).__name__}: {str(e)[:300]}")
        deps.event("error", type(e).__name__, None, str(e)[:200])
        out = AgentReply(reply=BUSY_REPLY)

    duration_ms = int((time.perf_counter() - started) * 1000)
    chat_usage = ChatUsage(
        requests=getattr(usage, "requests", 0) or 0,
        input_tokens=getattr(usage, "input_tokens", 0) or 0,
        output_tokens=getattr(usage, "output_tokens", 0) or 0,
        cached_input_tokens=getattr(usage, "cache_read_tokens", 0) or 0,
        tool_calls=len(deps.tool_log),
        duration_ms=duration_ms,
        model=MODEL_NAME,
    )
    log_run(
        {
            "reply_id": reply_id,
            "user_id": user_id,
            "message": message,
            "reply": out.reply,
            "product_ids": json.dumps(out.product_ids),
            "navigate": out.navigate.model_dump_json() if out.navigate else None,
            "tool_calls": json.dumps(deps.tool_log),
            "checks": json.dumps(deps.checks + [f"card attached by code: {pid}" for pid in deps.card_fixes]),
            "status": status,
            "model": MODEL_NAME,
            "requests": chat_usage.requests,
            "input_tokens": chat_usage.input_tokens,
            "output_tokens": chat_usage.output_tokens,
            "cached_input_tokens": chat_usage.cached_input_tokens,
            "duration_ms": duration_ms,
        }
    )
    append_audit(
        AuditEntry(
            run_id=reply_id,
            started_at=started_at,
            finished_at=_now(),
            duration_ms=duration_ms,
            shopper=f"user {user_id}" if user_id else "guest",
            page=f"{page.page_type} {page.path}" if page else None,
            message=message[:300],
            model=MODEL_NAME,
            events=_merge_model_steps(deps, messages),
            stop_reason=stop_reason,
            reply=out.reply[:300],
            product_ids=out.product_ids,
            model_requests=chat_usage.requests,
            tool_calls=chat_usage.tool_calls,
            input_tokens=chat_usage.input_tokens,
            output_tokens=chat_usage.output_tokens,
        )
    )
    return out, chat_usage, reply_id, deps.checks


# ---------- audit trail (append-only JSON) ----------


def _merge_model_steps(deps: Deps, messages: list[ModelMessage]) -> list[AuditEvent]:
    """Add one event per model response (what the model decided) to the tool/check events, in time order."""
    events = list(deps.events)
    for m in messages:
        if isinstance(m, ModelResponse):
            calls = [p.tool_name for p in m.parts if isinstance(p, ToolCallPart)]
            decided = "final answer" if calls == ["final_result"] else ("call tools: " + ", ".join(calls) if calls else "text")
            ts = m.timestamp.astimezone(timezone.utc) if m.timestamp else datetime.now(timezone.utc)
            ms = int((ts.timestamp() - deps.wall0) * 1000)
            events.append({"t": ts.isoformat(timespec="milliseconds"), "ms": max(ms, 0), "type": "model_response",
                           "name": decided, "args": None, "result": None})
        elif isinstance(m, ModelRequest):
            for p in m.parts:
                if isinstance(p, RetryPromptPart):
                    events.append({"t": _now(), "ms": int((time.perf_counter() - deps.t0) * 1000), "type": "retry_sent",
                                   "name": p.tool_name or "output", "args": None, "result": str(p.content)[:200]})
    events.sort(key=lambda e: e["ms"])
    return [AuditEvent(**e) for e in events]


def append_audit(entry: AuditEntry) -> None:
    """Append one entry to output/audit_trail.json without touching earlier entries.

    The file is a JSON array. It is created once; after that each run only removes the closing "]" at the very
    end and writes ",<new entry>]". Earlier bytes are never rewritten, and nothing ever truncates or recreates
    the file, so the trail survives server restarts ("not wiped between runs"). A file lock keeps concurrent
    requests from interleaving.
    """
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    blob = entry.model_dump_json(indent=2)
    with open(AUDIT_PATH, "a+b") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            if size == 0:
                f.write(("[\n" + blob + "\n]\n").encode())
                return
            # find the final "]" (skip trailing whitespace) and replace it with ",<entry>\n]"
            pos = size - 1
            while pos >= 0:
                f.seek(pos)
                ch = f.read(1)
                if ch not in (b"\n", b" ", b"\r", b"\t"):
                    break
                pos -= 1
            if ch != b"]":
                raise ValueError("audit_trail.json does not end with ']'; refusing to modify it")
            f.truncate(pos)  # removes only the closing bracket (and trailing whitespace)
            f.seek(pos)
            f.write((",\n" + blob + "\n]\n").encode())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
