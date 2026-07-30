"""TOTP MFA (RFC 6238) — stdlib only."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from typing import Any
from urllib.parse import quote

from app.db import audit, get_conn, now


def _base32_secret(length: int = 20) -> str:
    raw = secrets.token_bytes(length)
    return base64.b32encode(raw).decode("ascii").strip("=").upper()


def _decode_secret(secret: str) -> bytes:
    s = (secret or "").strip().replace(" ", "").upper()
    pad = (-len(s)) % 8
    return base64.b32decode(s + ("=" * pad), casefold=True)


def totp_at(secret: bytes, *, counter: int, digits: int = 6) -> str:
    msg = struct.pack(">Q", counter)
    digest = hmac.new(secret, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10**digits)).zfill(digits)


def verify_totp(secret: str, code: str, *, window: int = 1) -> bool:
    if not secret or not code:
        return False
    code = code.strip().replace(" ", "")
    if not code.isdigit() or len(code) not in {6, 8}:
        return False
    try:
        key = _decode_secret(secret)
    except Exception:
        return False
    counter = int(time.time()) // 30
    for delta in range(-window, window + 1):
        if hmac.compare_digest(totp_at(key, counter=counter + delta, digits=len(code)), code):
            return True
    return False


def mfa_status(user_id: str) -> dict[str, Any]:
    row = get_conn().execute(
        "SELECT mfa_enabled, mfa_secret FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if not row:
        return {"enabled": False, "enrolled": False}
    secret = row["mfa_secret"] or ""
    return {"enabled": bool(row["mfa_enabled"]), "enrolled": bool(secret)}


def mfa_enroll_start(user_id: str, *, issuer: str = "SecuraIQ", username: str = "") -> dict[str, Any]:
    secret = _base32_secret()
    c = get_conn()
    c.execute(
        "UPDATE users SET mfa_secret = ?, mfa_enabled = 0 WHERE id = ?",
        (secret, user_id),
    )
    c.commit()
    label = quote(f"{issuer}:{username or user_id}")
    uri = f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"
    audit("mfa_enroll_start", user_id, {})
    return {"secret": secret, "otpauth_uri": uri, "issuer": issuer}


def mfa_enroll_confirm(user_id: str, code: str) -> bool:
    row = get_conn().execute("SELECT mfa_secret FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row or not row["mfa_secret"]:
        raise ValueError("Start MFA enrollment first")
    if not verify_totp(row["mfa_secret"], code):
        raise ValueError("Invalid authenticator code")
    c = get_conn()
    c.execute("UPDATE users SET mfa_enabled = 1 WHERE id = ?", (user_id,))
    c.commit()
    audit("mfa_enroll_confirm", user_id, {})
    return True


def mfa_disable(user_id: str, code: str) -> bool:
    row = get_conn().execute(
        "SELECT mfa_secret, mfa_enabled FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if not row or not row["mfa_enabled"]:
        return True
    if not verify_totp(row["mfa_secret"] or "", code):
        raise ValueError("Invalid authenticator code")
    c = get_conn()
    c.execute(
        "UPDATE users SET mfa_enabled = 0, mfa_secret = '' WHERE id = ?",
        (user_id,),
    )
    c.commit()
    audit("mfa_disable", user_id, {})
    return True


def create_mfa_pending(user_id: str) -> str:
    token = secrets.token_urlsafe(24)
    expires = now() + 300
    c = get_conn()
    c.execute(
        "INSERT OR REPLACE INTO mfa_pending (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (token, user_id, expires, now()),
    )
    c.commit()
    return token


def consume_mfa_pending(token: str) -> str | None:
    th = (token or "").strip()
    if not th:
        return None
    c = get_conn()
    row = c.execute("SELECT user_id, expires_at FROM mfa_pending WHERE token = ?", (th,)).fetchone()
    if not row:
        return None
    c.execute("DELETE FROM mfa_pending WHERE token = ?", (th,))
    c.commit()
    if float(row["expires_at"]) < now():
        return None
    return row["user_id"]
