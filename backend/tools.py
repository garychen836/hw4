"""Database helpers and the read-only tools the shopping agent can call.

Every tool reads data/campus_customs.db through a read-only connection, so the
agent can never change prices, stock, or accounts. Tool results are kept short
(ids, names, prices, sizes) to keep each model call cheap.
"""

import json
import re
import sqlite3
from pathlib import Path

from models import (
    SIZES,
    ChatHistoryResult,
    PageContext,
    PageProduct,
    PageView,
    PastMessage,
    ShopperProfile,
    ProductCard,
    ProductDetails,
    ProductSummary,
    SearchResult,
    SizeStatus,
    SizeStock,
    SoldOutMatch,
    StockCheck,
    ToolError,
    stock_status,
)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "campus_customs.db"

# Words shoppers use -> words that appear in the catalogue.
SYNONYMS = {
    "tee": "t-shirt", "tees": "t-shirt", "tshirt": "t-shirt", "shirt": "t-shirt", "t-shirts": "t-shirt",
    "hoodies": "hoodie", "hooded": "hoodie", "hood": "hoodie",
    "sweatshirt": "crewneck", "sweatshirts": "crewneck", "crew": "crewneck", "crewnecks": "crewneck", "sweater": "sweater",
    "quarter": "1-4", "quarterzip": "1-4", "quarter-zip": "1-4", "1/4": "1-4", "zip": "zip",
    "jackets": "jacket", "fleece": "fleece",
    "grey": "gray", "blue": "blue", "navy": "navy",
    "mother": "mom", "father": "dad", "grandmother": "grandma", "grandfather": "grandpa",
}
# Umbrella words: a hit on any of these counts as a hit on the word.
EXPANSIONS = {
    # Family designs are matched by id prefix so "Brooks Brothers" doesn't count as "brother".
    "family": [f"yale-{w}-" for w in ("mom", "dad", "grandpa", "grandma", "brother", "sister", "uncle", "aunt", "cousin")],
    "parent": ["yale-mom-", "yale-dad-"], "parents": ["yale-mom-", "yale-dad-"],
    "grandparent": ["yale-grandpa-", "yale-grandma-"], "grandparents": ["yale-grandpa-", "yale-grandma-"],
    "college": ["college", "berkeley", "branford", "franklin", "davenport", "hopper", "edwards", "morse", "pierson", "saybrook", "silliman", "stiles", "dwight", "trumbull"],
    "sports": ["sports", "baseball", "basketball", "football", "hockey", "soccer", "tennis", "golf", "lacrosse", "sailing", "fencing", "squash", "diving", "swimming", "volleyball", "track"],
    "school": ["school", "law", "divinity", "forest", "medicine", "nursing", "management", "architecture", "engineering", "music", "art", "public health"],
}
STOPWORDS = {
    "a", "an", "the", "do", "you", "have", "any", "in", "for", "of", "and", "or", "with", "me", "my", "i", "is",
    "are", "show", "some", "yale", "want", "looking", "need", "something", "what", "your", "size", "sizes",
    "please", "can", "get", "to", "on", "that", "it", "this", "one", "items", "item", "stuff", "gear", "merch",
    "gift", "gifts", "present", "presents", "all", "options", "ideas", "idea", "good", "nice", "cool",
}


# ---------- shared database helpers (also used by main.py) ----------


def get_db() -> sqlite3.Connection:
    """Read-only connection: catalogue reads and agent tools never write."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def image_url_for(image_file_path: str) -> str:
    # Prefer the smoothed copy from backend/clean_images.py; fall back to the original photo.
    cleaned = DATA_DIR / "products_clean" / Path(image_file_path).name
    if cleaned.exists():
        return f"/media/products_clean/{cleaned.name}"
    return f"/media/{image_file_path}"


def product_from_row(row: sqlite3.Row) -> dict:
    return {
        "product_id": row["product_id"],
        "name": row["name"],
        "garment_type": row["garment_type"],
        "description": row["description"],
        "colors": json.loads(row["colors"] or "[]"),
        "search_tags": json.loads(row["search_tags"] or "[]"),
        "image_url": image_url_for(row["image_file_path"]),
        "price": row["price"],
    }


def inventory_for(conn: sqlite3.Connection, product_id: str) -> list[dict]:
    rows = conn.execute("SELECT size, quantity FROM inventory WHERE product_id = ?", (product_id,)).fetchall()
    sizes = [{"size": r["size"], "quantity": r["quantity"]} for r in rows]
    return sorted(sizes, key=lambda s: SIZES.index(s["size"]) if s["size"] in SIZES else 99)


def product_cards(product_ids: list[str]) -> list[ProductCard]:
    """Build cards for the chat widget from the database, keeping the requested order and skipping unknown ids."""
    cards = []
    with get_db() as conn:
        for pid in dict.fromkeys(product_ids):
            row = conn.execute("SELECT * FROM catalogue WHERE product_id = ?", (pid,)).fetchone()
            if row is None:
                continue
            inv = inventory_for(conn, pid)
            p = product_from_row(row)
            cards.append(
                ProductCard(
                    product_id=pid,
                    name=p["name"],
                    garment_type=p["garment_type"],
                    price=p["price"],
                    image_url=p["image_url"],
                    colors=p["colors"],
                    description=p["description"],
                    inventory=[SizeStock(**s) for s in inv],
                    total_stock=sum(s["quantity"] for s in inv),
                )
            )
    return cards


# ---------- search ----------


def _terms(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9/\-]+", text.lower())
    out = []
    for w in words:
        if w in STOPWORDS or len(w) < 2:
            continue
        out.append(SYNONYMS.get(w, w))
    return out


def _all_products(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM catalogue").fetchall()
    stock = {}
    for r in conn.execute("SELECT product_id, size, quantity FROM inventory"):
        stock.setdefault(r["product_id"], {})[r["size"]] = r["quantity"]
    products = []
    for row in rows:
        p = product_from_row(row)
        p["stock"] = stock.get(p["product_id"], {})
        p["haystack"] = " ".join(
            [p["product_id"], p["name"], p["garment_type"], p["description"], *p["colors"], *p["search_tags"]]
        ).lower()
        products.append(p)
    return products


def _main_color(p: dict) -> str | None:
    """Garment color. The catalogue lists the garment color first; later colors are usually the print."""
    return p["colors"][0] if p["colors"] else None


def _summary(p: dict) -> ProductSummary:
    """Short form for the model: enough to answer, cheap in tokens."""
    return ProductSummary(
        product_id=p["product_id"],
        name=p["name"],
        type=p["garment_type"],
        price=p["price"],
        main_color=_main_color(p),
        colors=p["colors"],
        in_stock_sizes=[s for s in SIZES if (p["stock"].get(s) or 0) > 0],
    )


def search_products(
    query: str = "",
    max_price: float | None = None,
    size_in_stock: str | None = None,
    limit: int = 6,
    match_all: bool = False,
) -> SearchResult | ToolError:
    """Search the catalogue by keywords (name, type, description, colors, tags).

    Optionally keep only items at or under max_price, or items that have size_in_stock (XS-XXL) available.
    Returns at most `limit` matches, best first, plus the total match count.
    match_all=True keeps only items matching every word (used by the Products page grid).
    Reads: catalogue (all fields) + inventory (quantity > 0 per size).
    """
    limit = max(1, min(limit, 200))
    size = size_in_stock.upper().strip() if size_in_stock else None
    if size and size not in SIZES:
        return ToolError(error=f"Unknown size '{size_in_stock}'. Sizes are {', '.join(SIZES)}.")
    terms = _terms(query)

    with get_db() as conn:
        products = _all_products(conn)

    scored, sold_out_in_size = [], []
    for p in products:
        if max_price is not None and p["price"] > max_price:
            continue
        if terms:
            hits = sum(1 for t in terms if any(alt in p["haystack"] for alt in EXPANSIONS.get(t, [t])))
            if hits == 0 or (match_all and hits < len(terms)):
                continue
            # Name/type hits count extra so "hockey hoodie" ranks the hockey hoodie first.
            title = f"{p['product_id']} {p['name']} {p['garment_type']}".lower()
            score = hits * 2 + sum(1 for t in terms if any(alt in title for alt in EXPANSIONS.get(t, [t]))) + (hits == len(terms)) * 3
        else:
            score = 0
        if size and (p["stock"].get(size) or 0) <= 0:
            sold_out_in_size.append((score, p))
            continue
        scored.append((score, sum(v or 0 for v in p["stock"].values()) > 0, p))

    scored.sort(key=lambda x: (-x[0], not x[1], x[2]["name"]))
    result = SearchResult(total_matches=len(scored), results=[_summary(p) for _, _, p in scored[:limit]])
    # Honesty: if a size filter hid strong matches, say so, so the agent can tell the shopper they're sold out.
    best = max((x[0] for x in scored[:1]), default=0)
    hidden = sorted((x for x in sold_out_in_size if x[0] >= best and x[0] > 0), key=lambda x: -x[0])[:3]
    result.sold_out_in_size = [
        SoldOutMatch(product_id=p["product_id"], name=p["name"], main_color=_main_color(p), price=p["price"])
        for _, p in hidden
    ]
    if not result.results:
        result.note = "No catalogue items match. Say we don't carry it; never invent an item."
    return result


def _resolve(product_id: str) -> str | None:
    """Turn a near-miss id ("saybrook-crewneck") into the real one when exactly one product matches every word.

    Saves the agent a second round trip; ambiguous guesses still return an error with suggestions.
    """
    terms = _terms(product_id.replace("-", " "))
    if not terms:
        return None
    with get_db() as conn:
        rows = conn.execute("SELECT product_id, name, garment_type FROM catalogue").fetchall()
    hits = [
        r["product_id"]
        for r in rows
        if all(any(alt in f"{r['product_id']} {r['name']} {r['garment_type']}".lower() for alt in EXPANSIONS.get(t, [t])) for t in terms)
    ]
    return hits[0] if len(hits) == 1 else None


def _not_found(product_id: str) -> ToolError:
    close = search_products(product_id.replace("-", " "), limit=3)
    ids = [c.product_id for c in close.results] if isinstance(close, SearchResult) else []
    return ToolError(error=f"No product with id '{product_id}'. Its price and stock are unclear.", did_you_mean=ids)


def get_product(product_id: str) -> ProductDetails | ToolError:
    """Full details for one product: description, price, colors, and stock for every size.

    Reads: catalogue (description, price, colors, garment_type, name) + inventory (quantity for all six sizes).
    A size with no inventory row is reported as quantity None / status "unclear", never guessed.
    """
    with get_db() as conn:
        row = conn.execute("SELECT * FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
        if row is None and (real := _resolve(product_id)):
            product_id = real
            row = conn.execute("SELECT * FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
        if row is None:
            return _not_found(product_id)
        p = product_from_row(row)
        qty = {s["size"]: s["quantity"] for s in inventory_for(conn, product_id)}
    sizes = [SizeStatus(size=s, quantity=qty.get(s), status=stock_status(qty.get(s))) for s in SIZES]
    return ProductDetails(
        product_id=p["product_id"],
        name=p["name"],
        type=p["garment_type"],
        price=p["price"],
        main_color=_main_color(p),
        colors=p["colors"],
        description=p["description"],
        sizes=sizes,
        total_in_stock=sum(s.quantity or 0 for s in sizes),
    )


def check_stock(product_id: str, size: str) -> StockCheck | ToolError:
    """Exact stock count for one product in one size (XS, S, M, L, XL, XXL).

    Reads: inventory.quantity for (product_id, size), plus catalogue.name and catalogue.price.
    """
    size = size.upper().strip()
    if size not in SIZES:
        return ToolError(error=f"Unknown size '{size}'. Sizes are {', '.join(SIZES)}.")
    with get_db() as conn:
        prod = conn.execute("SELECT name, price FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
        if prod is None and (real := _resolve(product_id)):
            product_id = real
            prod = conn.execute("SELECT name, price FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
        if prod is None:
            return _not_found(product_id)
        row = conn.execute(
            "SELECT quantity FROM inventory WHERE product_id = ? AND size = ?", (product_id, size)
        ).fetchone()
    qty = row["quantity"] if row else None
    return StockCheck(
        product_id=product_id, name=prod["name"], size=size, quantity=qty, status=stock_status(qty), price=prod["price"]
    )


# ---------- similar items ----------

_KIND_WORDS = [  # same buckets as the website's categories
    ("jacket", ("jacket", "full-zip", "full zip", "bomber")),
    ("quarter-zip", ("quarter-zip", "1-4-zip", "1 4 zip")),
    ("hoodie", ("hood",)),
    ("crewneck", ("crewneck", "mockneck", "sweater", "crew")),
    ("tee", ("t-shirt", "shirt", "tee", "long-sleeve")),
]
_THEMES = {  # what a design is "about"; similar items share it
    "college": ["benjamin-franklin", "berkeley", "branford", "davenport", "ezra-stiles", "grace-hopper", "jonathan-edwards",
                "morse", "pauli-murray", "pierson", "saybrook", "silliman", "timothy-dwight", "trumbull"],
    "sport": ["baseball", "basketball", "football", "hockey", "soccer", "tennis", "golf", "lacrosse", "sailing", "fencing",
              "squash", "diving", "swimming", "volleyball", "track", "crew-left"],
    "family": ["yale-mom", "yale-dad", "yale-grandpa", "yale-grandma", "yale-brother", "yale-uncle", "yale-aunt", "yale-cousin"],
    "school": ["school-of", "law-school", "divinity", "forest-school"],
    "bulldog": ["bulldog"],
}


def _kind(p: dict) -> str:
    text = f"{p['product_id']} {p['garment_type']}".lower()
    return next((k for k, words in _KIND_WORDS if any(w in text for w in words)), "other")


def _themes(p: dict) -> set[str]:
    pid = p["product_id"]
    return {t for t, words in _THEMES.items() if any(w in pid for w in words)}


def find_similar(product_id: str, size_in_stock: str | None = None, limit: int = 4) -> SearchResult | ToolError:
    """Items similar to one product: same garment kind and/or theme (college, sport, family, school, bulldog),
    closest garment color, in stock (optionally in a given size), best first. Excludes the product itself."""
    limit = max(1, min(limit, 6))
    size = size_in_stock.upper().strip() if size_in_stock else None
    if size and size not in SIZES:
        return ToolError(error=f"Unknown size '{size_in_stock}'. Sizes are {', '.join(SIZES)}.")
    with get_db() as conn:
        products = _all_products(conn)
    by_id = {p["product_id"]: p for p in products}
    base = by_id.get(product_id) or by_id.get(_resolve(product_id) or "")
    if base is None:
        return _not_found(product_id)
    kind, themes, color = _kind(base), _themes(base), (_main_color(base) or "").lower()
    scored = []
    for p in products:
        if p["product_id"] == base["product_id"]:
            continue
        stock = p["stock"]
        if size and (stock.get(size) or 0) <= 0:
            continue
        if not size and sum(v or 0 for v in stock.values()) == 0:
            continue
        score = 3 * (_kind(p) == kind) + 2 * len(themes & _themes(p))
        pc = (_main_color(p) or "").lower()
        if color and pc and (color in pc or pc in color or color.split()[-1] == pc.split()[-1]):
            score += 1
        if score >= 3:  # at least the same kind of garment, or a shared theme plus color
            scored.append((score, abs(p["price"] - base["price"]), p))
    scored.sort(key=lambda x: (-x[0], x[1], x[2]["name"]))
    result = SearchResult(total_matches=len(scored), results=[_summary(p) for _, _, p in scored[:limit]])
    if not result.results:
        result.note = "No similar items in stock" + (f" in {size}." if size else ".")
    else:
        shared = f"same kind of garment ({kind})" + (f" and/or the same theme ({', '.join(sorted(themes))})" if themes else "")
        result.note = f"Similar to {base['name']} by {shared}. They are different designs; describe each by its own name."
    return result


# ---------- who is chatting / chat history / current page ----------


def shopper_profile(user_id: int) -> ShopperProfile | None:
    """The logged-in shopper's own profile from the users table (never the password hash)."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, name, first_name, last_name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    if row is None:
        return None
    return ShopperProfile(
        user_id=row["id"],
        name=row["name"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        email=row["email"],
        username=row["email"].split("@")[0],
        member_since=row["created_at"],
    )


def chat_history(user_id: int | None, query: str = "", limit: int = 10) -> ChatHistoryResult:
    """The shopper's own earlier chat messages (oldest first), optionally only those mentioning `query`.

    Reads chat_messages for this user_id only; there is no way to read another shopper's chat.
    """
    if user_id is None:
        return ChatHistoryResult(logged_in=False, note="Guest: past chats are not saved. Suggest logging in to keep history.")
    limit = max(1, min(limit, 20))
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM chat_messages WHERE user_id = ?", (user_id,)).fetchone()[0]
        sql = "SELECT role, content, products_json, created_at FROM chat_messages WHERE user_id = ?"
        args: list = [user_id]
        if query.strip():
            sql += " AND content LIKE ?"
            args.append(f"%{query.strip()}%")
        rows = conn.execute(sql + " ORDER BY id DESC LIMIT ?", (*args, limit)).fetchall()
    messages = []
    for r in reversed(rows):
        names = [p.get("name", "") for p in json.loads(r["products_json"] or "[]") if isinstance(p, dict)]
        text = r["content"] if len(r["content"]) <= 400 else r["content"][:400] + "…"
        messages.append(PastMessage(role=r["role"], content=text, product_names=names[:6], created_at=r["created_at"]))
    note = None if messages else ("No earlier messages match." if query else "No earlier chats yet.")
    return ChatHistoryResult(logged_in=True, total_messages=total, messages=messages, note=note)


def current_page(page: PageContext | None) -> PageView:
    """Resolve what the shopper is looking at (sent by the website) against the database."""
    if page is None:
        return PageView(page_type="other", path="unknown")
    viewing = None
    if page.product_id:
        details = get_product(page.product_id)
        viewing = details if isinstance(details, ProductDetails) else None
    results = []
    if page.results_product_ids:
        for c in product_cards(page.results_product_ids):
            results.append(
                PageProduct(product_id=c.product_id, name=c.name, price=c.price, main_color=c.colors[0] if c.colors else None)
            )
    filters = {k: v for k, v in {"search": page.search, "category": page.category, "collection": page.collection}.items() if v}
    size = page.selected_size.upper() if page.selected_size and page.selected_size.upper() in SIZES else None
    bigger, smaller = [], []
    if viewing and size:
        i = SIZES.index(size)
        bigger = [s for s in viewing.sizes if SIZES.index(s.size) > i]
        smaller = [s for s in reversed(viewing.sizes) if SIZES.index(s.size) < i]
    return PageView(
        page_type=page.page_type,
        path=page.path,
        viewing=viewing,
        selected_size=size,
        bigger_sizes=bigger,
        smaller_sizes=smaller,
        filters=filters,
        results_title=page.results_title,
        results_on_page=results,
    )


# ---------- privacy ----------

_CARD_RE = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def redact(text: str) -> str:
    """Remove card numbers and SSNs before a message is logged, stored, or sent to the model."""
    text = _CARD_RE.sub("[card number removed]", text)
    return _SSN_RE.sub("[ID number removed]", text)
