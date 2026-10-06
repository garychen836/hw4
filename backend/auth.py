"""Accounts: sign up, log in, log out, and "who am I".

Security choices (see output/harness.md for the plain-language version):
- Passwords are stored only as PBKDF2-SHA256 hashes with a random per-user salt,
  in the same `pbkdf2_sha256$<salt>$<hex digest>` format as the existing users.
- Logins create a random session token sent as an HttpOnly cookie; the database
  stores only the SHA-256 of the token, so a leaked database cannot be replayed.
- Login errors never say whether the email exists, and repeated failures are
  rate-limited per email and per IP address.
- All SQL uses parameters; the password hash is never returned to the browser.
"""

import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

# Must match the seed database's hashes: the stored format has no iteration field,
# so every account uses the same count (the seed users were hashed with 120,000).
PBKDF2_ITERATIONS = 120_000
SESSION_COOKIE = "cc_session"
SESSION_DAYS = 7
MAX_FAILED_PER_EMAIL = 5  # guessing one account's password ...
MAX_FAILED_PER_IP = 20  # ... or spraying many accounts from one address ...
FAILED_LOGIN_WINDOW = 15 * 60  # ... within 15 minutes
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

router = APIRouter(prefix="/api/auth", tags=["auth"])
_db_path = None  # set by init()
_failed: dict[str, deque] = defaultdict(deque)


def init(db_path) -> None:
    """Remember the database path and create the sessions table if needed."""
    global _db_path
    _db_path = db_path
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ---------- password hashing ----------


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt, _ = stored.split("$")
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    return hmac.compare_digest(hash_password(password, salt), stored)


# A fixed hash to check against when the email doesn't exist, so a login for an
# unknown email takes as long as a wrong password (no timing hint).
_DUMMY_HASH = hash_password(secrets.token_hex(16))


# ---------- rate limiting ----------


def _too_many_failures(*keys: str) -> bool:
    now = time.monotonic()
    for key in keys:
        q = _failed[key]
        while q and now - q[0] > FAILED_LOGIN_WINDOW:
            q.popleft()
        limit = MAX_FAILED_PER_IP if key.startswith("ip:") else MAX_FAILED_PER_EMAIL
        if len(q) >= limit:
            return True
    return False


def _record_failure(*keys: str) -> None:
    now = time.monotonic()
    for key in keys:
        _failed[key].append(now)


# ---------- sessions ----------


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _start_session(conn: sqlite3.Connection, response: Response, user_id: int) -> None:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (_token_hash(token), user_id, expires.strftime("%Y-%m-%d %H:%M:%S")),
    )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 3600,
        httponly=True,  # page scripts can't read it
        samesite="lax",  # not sent on cross-site form posts
        secure=False,  # set True when served over HTTPS
        path="/",
    )


def current_user(token: str | None) -> dict | None:
    """Return the logged-in user for a session token, or None."""
    if not token:
        return None
    with connect() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.name, u.first_name, u.last_name, u.email, u.created_at
            FROM sessions s JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ? AND s.expires_at > datetime('now')
            """,
            (_token_hash(token),),
        ).fetchone()
    return public_user(row) if row else None


def public_user(row: sqlite3.Row) -> dict:
    # Only safe fields; never the password hash.
    return {
        "id": row["id"],
        "name": row["name"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "email": row["email"],
        "created_at": row["created_at"],
    }


# ---------- request models ----------


def _clean_email(v: str) -> str:
    v = v.strip().lower()
    if not EMAIL_RE.match(v) or len(v) > 254:
        raise ValueError("Enter a valid email address.")
    return v


class SignupRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    email: str
    password: str = Field(max_length=128)

    @field_validator("first_name", "last_name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Name is required.")
        if any(c in v for c in "<>{}$;\\"):
            raise ValueError("Name contains characters that aren't allowed.")
        return v

    @field_validator("email")
    @classmethod
    def clean_email(cls, v: str) -> str:
        return _clean_email(v)

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("Password must include at least one letter and one number.")
        return v


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


# ---------- endpoints ----------


@router.post("/signup", status_code=201)
def signup(req: SignupRequest, response: Response) -> dict:
    with connect() as conn:
        exists = conn.execute("SELECT 1 FROM users WHERE email = ?", (req.email,)).fetchone()
        if exists:
            raise HTTPException(409, "An account with this email already exists. Try logging in.")
        cur = conn.execute(
            """
            INSERT INTO users (name, first_name, last_name, email, password_hash)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                f"{req.first_name} {req.last_name}",
                req.first_name,
                req.last_name,
                req.email,
                hash_password(req.password),
            ),
        )
        user_id = cur.lastrowid
        _start_session(conn, response, user_id)
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return {"user": public_user(row)}


@router.post("/login")
def login(req: LoginRequest, request: Request, response: Response) -> dict:
    email = req.email.strip().lower()
    ip = request.client.host if request.client else "unknown"
    keys = (f"email:{email}", f"ip:{ip}")
    if _too_many_failures(*keys):
        raise HTTPException(429, "Too many failed attempts. Please wait 15 minutes and try again.")

    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        ok = verify_password(req.password, row["password_hash"] if row else _DUMMY_HASH)
        if not row or not ok:
            _record_failure(*keys)
            raise HTTPException(401, "Incorrect email or password.")
        _start_session(conn, response, row["id"])
    _failed.pop(f"email:{email}", None)
    return {"user": public_user(row)}


@router.post("/logout")
def logout(response: Response, cc_session: str | None = Cookie(default=None)) -> dict:
    if cc_session:
        with connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(cc_session),))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(cc_session: str | None = Cookie(default=None)) -> dict:
    return {"user": current_user(cc_session)}
