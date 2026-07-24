"""Local auth: users, sessions, API keys (stdlib crypto)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.db import audit, get_conn, new_id, now, row_to_dict

SESSION_DAYS = 14


@dataclass
class AuthUser:
    id: str
    username: str
    role: str


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 180_000)
    return f"pbkdf2${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt, hexdigest = stored.split("$", 2)
        if algo != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 180_000)
        return hmac.compare_digest(dk.hex(), hexdigest)
    except Exception:
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def ensure_bootstrap_admin() -> str | None:
    """Create default admin if no users exist. Returns plaintext password once if created."""
    c = get_conn()
    row = c.execute("SELECT COUNT(*) AS n FROM users").fetchone()
    if row and int(row["n"]) > 0:
        return None
    password = settings.bootstrap_admin_password or secrets.token_urlsafe(12)
    uid = new_id()
    c.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
        (uid, settings.bootstrap_admin_username, hash_password(password), "admin", now()),
    )
    c.commit()
    audit("bootstrap_admin", uid, {"username": settings.bootstrap_admin_username})
    print(
        f"SecuraIQ auth: created admin `{settings.bootstrap_admin_username}` "
        f"(set BOOTSTRAP_ADMIN_PASSWORD to choose; password was auto-generated if unset)."
    )
    if not settings.bootstrap_admin_password:
        print(f"SecuraIQ auth: one-time admin password → {password}")
        return password
    return None


def register_user(username: str, password: str, role: str = "user") -> AuthUser:
    username = (username or "").strip().lower()
    if len(username) < 3 or len(password) < 8:
        raise ValueError("Username ≥3 chars and password ≥8 chars required")
    c = get_conn()
    uid = new_id()
    try:
        c.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (uid, username, hash_password(password), role, now()),
        )
        c.commit()
    except Exception as exc:
        raise ValueError("Username already taken") from exc
    audit("register", uid, {"username": username})
    return AuthUser(id=uid, username=username, role=role)


def login(username: str, password: str) -> tuple[AuthUser, str]:
    c = get_conn()
    row = c.execute(
        "SELECT * FROM users WHERE username = ?",
        ((username or "").strip().lower(),),
    ).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        raise ValueError("Invalid username or password")
    token = secrets.token_urlsafe(32)
    expires = now() + SESSION_DAYS * 86400
    c.execute(
        "INSERT INTO sessions (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (hash_token(token), row["id"], expires, now()),
    )
    c.commit()
    audit("login", row["id"], {"username": row["username"]})
    return AuthUser(id=row["id"], username=row["username"], role=row["role"]), token


def logout(token: str | None) -> None:
    if not token:
        return
    c = get_conn()
    c.execute("DELETE FROM sessions WHERE token = ?", (hash_token(token),))
    c.commit()


def create_api_key(user_id: str, name: str = "default") -> tuple[str, dict[str, Any]]:
    raw = "hg_" + secrets.token_urlsafe(28)
    kid = new_id()
    c = get_conn()
    c.execute(
        "INSERT INTO api_keys (id, user_id, name, key_prefix, key_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (kid, user_id, name or "default", raw[:10], hash_token(raw), now()),
    )
    c.commit()
    audit("api_key_create", user_id, {"name": name, "prefix": raw[:10]})
    return raw, {"id": kid, "name": name, "key_prefix": raw[:10]}


def resolve_user(authorization: str | None, api_key_header: str | None = None) -> AuthUser | None:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token and api_key_header:
        token = api_key_header.strip()
    if not token:
        return None

    c = get_conn()
    th = hash_token(token)

    # Session token
    sess = c.execute(
        "SELECT u.id, u.username, u.role, s.expires_at FROM sessions s "
        "JOIN users u ON u.id = s.user_id WHERE s.token = ?",
        (th,),
    ).fetchone()
    if sess:
        if float(sess["expires_at"]) < now():
            c.execute("DELETE FROM sessions WHERE token = ?", (th,))
            c.commit()
            return None
        return AuthUser(id=sess["id"], username=sess["username"], role=sess["role"])

    # API key
    key = c.execute(
        "SELECT u.id, u.username, u.role FROM api_keys k "
        "JOIN users u ON u.id = k.user_id WHERE k.key_hash = ?",
        (th,),
    ).fetchone()
    if key:
        return AuthUser(id=key["id"], username=key["username"], role=key["role"])
    return None


def list_users_public() -> list[dict[str, Any]]:
    c = get_conn()
    rows = c.execute("SELECT id, username, role, created_at FROM users ORDER BY created_at").fetchall()
    return [dict(r) for r in rows]
