"""Pydantic / PydanticAI types shared by the API, the agent, and its tools."""

from typing import Literal

from pydantic import BaseModel, Field

SIZES = ("XS", "S", "M", "L", "XL", "XXL")


# ---------- catalogue ----------


class SizeStock(BaseModel):
    size: str
    quantity: int


class ProductCard(BaseModel):
    """What the chat widget shows for one product (always built from the database, never by the model)."""

    product_id: str
    name: str
    garment_type: str
    price: float
    image_url: str
    colors: list[str] = []
    description: str = ""
    inventory: list[SizeStock] = []
    total_stock: int = 0


# ---------- tool return types (what the agent sees from campus_customs.db) ----------

StockStatus = Literal["in_stock", "low_stock", "sold_out", "unclear"]
LOW_STOCK_MAX = 5  # 1-5 units counts as low stock ("only N left")


def stock_status(quantity: int | None) -> StockStatus:
    """One rule for every tool: None means the database has no row for it, so we can't confirm."""
    if quantity is None:
        return "unclear"
    if quantity <= 0:
        return "sold_out"
    return "low_stock" if quantity <= LOW_STOCK_MAX else "in_stock"


class ProductSummary(BaseModel):
    """One search hit: enough to recommend an item without a second lookup."""

    product_id: str
    name: str
    type: str = Field(description="catalogue.garment_type")
    price: float = Field(description="catalogue.price in USD, exact")
    main_color: str | None = Field(description="Garment color (first entry of catalogue.colors); None if not listed")
    colors: list[str]
    in_stock_sizes: list[str] = Field(description="Sizes with inventory.quantity > 0 (no counts)")


class SoldOutMatch(BaseModel):
    product_id: str
    name: str
    main_color: str | None
    price: float


class SearchResult(BaseModel):
    total_matches: int
    results: list[ProductSummary]
    sold_out_in_size: list[SoldOutMatch] = Field(
        default_factory=list,
        description="Strong matches hidden only because the requested size is sold out (quantity 0).",
    )
    note: str | None = None


class SizeStatus(BaseModel):
    size: str
    quantity: int | None = Field(description="inventory.quantity; None if the database has no row for this size")
    status: StockStatus


class ProductDetails(BaseModel):
    """Everything about one product: description, price, and stock for every size."""

    product_id: str
    name: str
    type: str
    price: float
    main_color: str | None
    colors: list[str]
    description: str
    sizes: list[SizeStatus]
    total_in_stock: int


class StockCheck(BaseModel):
    """Exact stock for one product in one size."""

    product_id: str
    name: str
    size: str
    quantity: int | None
    status: StockStatus
    price: float


class ToolError(BaseModel):
    """Returned instead of guessing when the database can't answer."""

    error: str
    did_you_mean: list[str] = []


# ---------- agent output ----------


class NavigateAction(BaseModel):
    """Optional: take the shopper to a page. Only used when they ask to go somewhere or see a list."""

    type: Literal["product", "products"] = Field(
        description="'product' opens one product page; 'products' opens the Products page filtered by a search or collection."
    )
    product_id: str | None = Field(default=None, description="For type='product': the exact product_id from a tool result.")
    search: str | None = Field(default=None, description="For type='products': a short keyword search, e.g. 'hockey'.")
    collection: Literal["colleges", "sports", "family", "schools", "classics"] | None = Field(
        default=None, description="For type='products': one of the home-page collections."
    )


class AgentReply(BaseModel):
    """Structured answer the agent must return. The backend checks it before the shopper sees it."""

    reply: str = Field(description="Friendly answer for the shopper, 1-4 short sentences. Plain text, no markdown tables.")
    product_ids: list[str] = Field(
        default_factory=list,
        max_length=6,
        description="Up to 6 product_ids (copied exactly from tool results) to show as cards under the reply.",
    )
    results_title: str | None = Field(
        default=None,
        max_length=40,
        description="Short heading for the product cards shown on the page, e.g. 'Navy hoodies in M'. Set whenever product_ids is not empty.",
    )
    navigate: NavigateAction | None = Field(
        default=None, description="Only when the shopper explicitly asks to go to a product page or the full Products page."
    )
    suggestions: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="Up to 3 short follow-up questions the shopper might tap next (each under 40 characters).",
    )


# ---------- who is chatting, and what they are looking at ----------


class ShopperProfile(BaseModel):
    """The logged-in shopper, from the users table. Never includes the password hash."""

    user_id: int
    name: str
    first_name: str | None = None
    last_name: str | None = None
    email: str
    username: str = Field(description="Part of the email before @ (the users table has no separate username)")
    member_since: str = Field(description="users.created_at")


class PageContext(BaseModel):
    """What the shopper is looking at when they send a message (sent by the website with every chat message)."""

    path: str = Field(default="/", max_length=200, description="Current URL path and query, e.g. /products/boola-boola-t-shirt")
    page_type: Literal["home", "products", "product", "about", "login", "signup", "other"] = "other"
    product_id: str | None = Field(default=None, max_length=120, description="Product open on a single-item page")
    selected_size: str | None = Field(default=None, max_length=5, description="Size selected in the size picker")
    search: str | None = Field(default=None, max_length=100, description="Search box text on the Products page")
    category: str | None = Field(default=None, max_length=60)
    collection: str | None = Field(default=None, max_length=40)
    results_title: str | None = Field(default=None, max_length=60, description="Heading of the chat results shown on the page")
    results_product_ids: list[str] = Field(
        default_factory=list, max_length=12, description="Products currently shown in 'Matching items from your chat', in order"
    )


class PageProduct(BaseModel):
    product_id: str
    name: str
    price: float
    main_color: str | None


class PageView(BaseModel):
    """get_current_page tool result: the page context resolved against the database."""

    page_type: str
    path: str
    viewing: ProductDetails | None = Field(default=None, description="Full details of the product open on the page")
    selected_size: str | None = None
    bigger_sizes: list[SizeStatus] = Field(default_factory=list, description="Sizes above the selected size, smallest first, with stock")
    smaller_sizes: list[SizeStatus] = Field(default_factory=list, description="Sizes below the selected size, largest first, with stock")
    filters: dict[str, str] = Field(default_factory=dict, description="search / category / collection on the Products page")
    results_title: str | None = None
    results_on_page: list[PageProduct] = Field(default_factory=list, description="Chat results shown on the page, in order")


class PastMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    product_names: list[str] = []
    created_at: str


class ChatHistoryResult(BaseModel):
    """get_chat_history tool result: the logged-in shopper's earlier messages (oldest first)."""

    logged_in: bool
    total_messages: int = 0
    messages: list[PastMessage] = []
    note: str | None = None


# ---------- chat API ----------


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    # Recent turns for guests. Logged-in shoppers' history is loaded from the database instead.
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)
    page: PageContext | None = Field(default=None, description="What the shopper is looking at")


class ChatUsage(BaseModel):
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0  # input tokens the provider served from its prompt cache (billed at a discount)
    tool_calls: int = 0
    duration_ms: int = 0
    model: str = ""


class ChatResponse(BaseModel):
    message_id: int | None = Field(default=None, description="chat_messages.id of the reply (logged-in shoppers), for feedback.")
    reply_id: str = Field(description="Unique id of this reply, used to send feedback.")
    reply: str
    products: list[ProductCard] = Field(
        default_factory=list, description="Matching items, in order. The website renders them on the page as product cards."
    )
    results_title: str | None = Field(default=None, description="Heading for the on-page results section.")
    results_query: str | None = Field(default=None, description="Keywords of the agent's last catalogue search (for 'See all').")
    results_total: int | None = Field(default=None, description="How many catalogue items matched that search.")
    navigate: NavigateAction | None = None
    suggestions: list[str] = []
    checks: list[str] = Field(default_factory=list, description="Internal sanity-check notes (empty when all checks passed).")
    usage: ChatUsage = ChatUsage()


class FeedbackRequest(BaseModel):
    reply_id: str = Field(max_length=64)
    helpful: bool | None = None
    accurate: bool | None = None
    comment: str | None = Field(default=None, max_length=500)


# ---------- audit trail (output/audit_trail.json, append-only) ----------


class AuditEvent(BaseModel):
    """One step inside an agent run."""

    t: str = Field(description="UTC timestamp, ISO 8601")
    ms: int = Field(description="Milliseconds since the run started")
    type: Literal["small_talk", "model_response", "tool_call", "check_failed", "repeat_blocked", "retry_sent", "error"]
    name: str | None = Field(default=None, description="Tool name, or what the model decided (e.g. 'final answer')")
    args: dict | None = Field(default=None, description="Tool arguments (long strings shortened)")
    result: str | None = Field(default=None, description="Short summary of the tool result or problem")


class AuditEntry(BaseModel):
    """One shopper message and everything the agent did to answer it."""

    run_id: str = Field(description="Same as chat_runs.reply_id / chat_feedback.reply_id")
    started_at: str
    finished_at: str
    duration_ms: int
    shopper: str = Field(description="'user <id>' or 'guest' (never a name or email)")
    page: str | None = Field(default=None, description="Page type and path the shopper was on")
    message: str = Field(description="The shopper's message (card numbers/SSNs already redacted, max 300 chars)")
    model: str
    events: list[AuditEvent]
    stop_reason: str = Field(
        description="final_answer | final_answer_after_fix | small_talk | fallback_check_failed | fallback_usage_limit | error"
    )
    reply: str = Field(description="What the shopper saw (max 300 chars)")
    product_ids: list[str] = []
    model_requests: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

