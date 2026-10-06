"""Campus Customs API (FastAPI).

Serves the product catalogue, stock by size, and product images from
data/campus_customs.db; account sign up / log in (auth.py); and the shopping
chat, whose brain is the PydanticAI agent in agent.py.

Run from the backend folder:
    cd backend && ../.venv/bin/uvicorn main:app --reload --port 8000
(or from the HW 4 folder: .venv/bin/uvicorn backend.main:app --reload --port 8000)
"""

import json
import sqlite3
import sys
import time
from collections import defaultdict, deque
from pathlib import Path

# Make sibling modules importable both as `uvicorn main:app` (from backend/) and `uvicorn backend.main:app`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import Cookie, FastAPI, HTTPException, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

import agent  # noqa: E402
import auth  # noqa: E402
from models import ChatRequest, ChatResponse, ChatTurn, FeedbackRequest  # noqa: E402
from tools import (  # noqa: E402
    DATA_DIR,
    DB_PATH,
    get_db,
    inventory_for,
    product_cards,
    product_from_row,
    redact,
    shopper_profile,
)
from tools import search_products as tools_search  # noqa: E402

CHAT_LIMIT_PER_MINUTE = 15  # per IP address: protects the API budget from floods and scripts

app = FastAPI(title="Campus Customs API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Product photos only. Never mount all of data/: that would expose the database file.
app.mount("/media/products_clean", StaticFiles(directory=DATA_DIR / "products_clean", check_dir=False), name="media_clean")
app.mount("/media/products", StaticFiles(directory=DATA_DIR / "products"), name="media")

auth.init(DB_PATH)
agent.init_run_log()


def init_chat_history() -> None:
    """Upgrade the seed chat_messages table in place (keeps the original columns and rows)."""
    with sqlite3.connect(DB_PATH) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(chat_messages)")}
        if "page_json" not in cols:
            conn.execute("ALTER TABLE chat_messages ADD COLUMN page_json TEXT")  # what the shopper was viewing
        if "reply_id" not in cols:
            conn.execute("ALTER TABLE chat_messages ADD COLUMN reply_id TEXT")  # links a turn to chat_runs / chat_feedback
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_user ON chat_messages (user_id, id)")


init_chat_history()
app.include_router(auth.router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "model": agent.MODEL_NAME}


# ---------- catalogue ----------


@app.get("/api/products")
def list_products() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT c.*, COALESCE(SUM(i.quantity), 0) AS total_stock
            FROM catalogue c LEFT JOIN inventory i ON i.product_id = c.product_id
            GROUP BY c.product_id
            ORDER BY c.name
            """
        ).fetchall()
    return [{**product_from_row(r), "total_stock": r["total_stock"]} for r in rows]


@app.get("/api/search")
def search(q: str = "") -> dict:
    """Catalogue search for the Products page: the same ranking, synonyms, and plurals the agent uses."""
    return {"query": q.strip()[:100], "product_ids": page_search(q)}


def page_search(q: str) -> list[str]:
    """Items matching every word (falls back to any word if nothing matches all), best first."""
    q = q.strip()[:100]
    if not q:
        return []
    for match_all in (True, False):
        result = tools_search(q, limit=200, match_all=match_all)
        if hasattr(result, "results") and result.results:
            return [r.product_id for r in result.results]
    return []


@app.get("/api/products/{product_id}")
def get_product(product_id: str) -> dict:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Product not found")
        inventory = inventory_for(conn, product_id)
    return {
        **product_from_row(row),
        "inventory": inventory,
        "total_stock": sum(s["quantity"] for s in inventory),
    }


# ---------- chat ----------

_chat_hits: dict[str, deque] = defaultdict(deque)


def _rate_limited(ip: str) -> bool:
    now = time.monotonic()
    q = _chat_hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= CHAT_LIMIT_PER_MINUTE:
        return True
    q.append(now)
    return False


def _write_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _saved_history(user_id: int, limit: int = agent.MAX_HISTORY_TURNS) -> list[ChatTurn]:
    with _write_db() as conn:
        rows = conn.execute(
            "SELECT role, content FROM chat_messages WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)
        ).fetchall()
    return [ChatTurn(role=r["role"], content=r["content"]) for r in reversed(rows) if r["role"] in ("user", "assistant")]


@app.post("/api/chat")
async def chat(req: ChatRequest, request: Request, cc_session: str | None = Cookie(default=None)) -> ChatResponse:
    ip = request.client.host if request.client else "unknown"
    if _rate_limited(ip):
        raise HTTPException(429, "You're sending messages very quickly. Please wait a minute and try again.")

    user = auth.current_user(cc_session)
    profile = shopper_profile(user["id"]) if user else None  # who is chatting (agent deps)
    message = redact(req.message.strip())  # never log, store, or send card numbers / SSNs
    # Logged-in shoppers: memory comes from the database. Guests: from the recent turns the widget sends.
    history = _saved_history(user["id"]) if user else [ChatTurn(role=t.role, content=redact(t.content)) for t in req.history]
    run_deps: list = []
    out, usage, reply_id, checks = await agent.answer(message, history, profile=profile, page=req.page, deps_out=run_deps)
    last_search = run_deps[0].last_search if run_deps else None
    if last_search:  # count what the Products page will actually show for that search
        last_search = (last_search[0], len(page_search(last_search[0])))
    cards = product_cards(out.product_ids)

    message_id = None
    if user:
        with _write_db() as conn:
            page_json = req.page.model_dump_json(exclude_defaults=True) if req.page else None
            conn.execute(
                "INSERT INTO chat_messages (user_id, role, content, page_json, reply_id) VALUES (?, 'user', ?, ?, ?)",
                (user["id"], message, page_json, reply_id),
            )
            cur = conn.execute(
                "INSERT INTO chat_messages (user_id, role, content, products_json, page_json, reply_id) "
                "VALUES (?, 'assistant', ?, ?, ?, ?)",
                (user["id"], out.reply, json.dumps([c.model_dump() for c in cards]) if cards else None, page_json, reply_id),
            )
            message_id = cur.lastrowid

    return ChatResponse(
        message_id=message_id,
        reply_id=reply_id,
        reply=out.reply,
        products=cards,
        results_title=(out.results_title or None) if cards else None,
        # "See all N matches" only when the search found more than the cards shown.
        results_query=last_search[0] if cards and last_search and last_search[1] > len(cards) else None,
        results_total=last_search[1] if cards and last_search and last_search[1] > len(cards) else None,
        navigate=out.navigate,
        suggestions=out.suggestions,
        checks=checks,
        usage=usage,
    )


@app.get("/api/chat/history")
def chat_history(cc_session: str | None = Cookie(default=None)) -> dict:
    """Saved conversation for the logged-in shopper (empty for guests)."""
    user = auth.current_user(cc_session)
    if not user:
        return {"messages": []}
    with _write_db() as conn:
        rows = conn.execute(
            "SELECT id, role, content, products_json, reply_id, created_at FROM chat_messages "
            "WHERE user_id = ? ORDER BY id DESC LIMIT 30",
            (user["id"],),
        ).fetchall()
    return {
        "messages": [
            {
                "role": r["role"],
                "content": r["content"],
                "products": json.loads(r["products_json"] or "[]"),
                "reply_id": r["reply_id"],
                "created_at": r["created_at"],
            }
            for r in reversed(rows)
        ]
    }


@app.post("/api/chat/feedback")
def chat_feedback(req: FeedbackRequest, cc_session: str | None = Cookie(default=None)) -> dict:
    """After-service survey: was this reply helpful / accurate, plus an optional note."""
    user = auth.current_user(cc_session)
    with _write_db() as conn:
        run = conn.execute("SELECT user_id FROM chat_runs WHERE reply_id = ?", (req.reply_id,)).fetchone()
        if run is None:
            raise HTTPException(404, "Unknown reply.")
        if run["user_id"] is not None and (not user or user["id"] != run["user_id"]):
            raise HTTPException(403, "You can only rate your own conversation.")
        conn.execute(
            "INSERT INTO chat_feedback (reply_id, user_id, helpful, accurate, comment) VALUES (?, ?, ?, ?, ?)",
            (req.reply_id, (user or {}).get("id"), req.helpful, req.accurate, (req.comment or "").strip() or None),
        )
    return {"ok": True}
