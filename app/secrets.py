"""Secret masking helpers — never expose raw tokens via API/UI."""

from __future__ import annotations

import re
from typing import Any

# Values that look like UI placeholders / masks — never persist these.
_MASK_PLACEHOLDERS = {
    "",
    "*",
    "********",
    "••••••••",
    "••••",
    "...",
    "…",
    "<hidden>",
    "[hidden]",
    "redacted",
}

_SECRET_SUFFIXES = ("_api_key", "_token", "_secret", "_password")
_SECRET_EXACT = {
    "hf_token",
    "jira_api_token",
    "openai_compat_api_key",
    "hermes_api_key",
    "hermes_session_key",
    "openai_api_key",
    "openrouter_api_key",
    "groq_api_key",
    "together_api_key",
    "fireworks_api_key",
}

# Redact common secret shapes if they appear in logs/errors.
_REDACT_PATTERNS = [
    re.compile(r"\bhf_[A-Za-z0-9._\-]{8,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9\-._~+/]+=*\b", re.IGNORECASE),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?([^\s'\"]{6,})"),
]


def is_secret_field(name: str) -> bool:
    n = (name or "").strip().lower()
    if n in _SECRET_EXACT:
        return True
    return any(n.endswith(suf) for suf in _SECRET_SUFFIXES)


def is_blank_or_placeholder(value: Any) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    v = value.strip()
    if v.lower() in _MASK_PLACEHOLDERS:
        return True
    if set(v) <= {"*", "•", ".", "…"}:
        return True
    # Masked preview forms like "hf_a…xyz1"
    if "…" in v or "..." in v:
        return True
    return False


def mask_secret(value: str | None) -> str:
    """Opaque mask only — never return real token characters."""
    if not (value or "").strip():
        return ""
    return "••••••••"


def secret_status(value: str | None) -> dict[str, Any]:
    set_ = bool((value or "").strip())
    return {
        "set": set_,
        "masked": mask_secret(value) if set_ else "",
    }


def redact_text(text: str) -> str:
    if not text:
        return text
    out = str(text)
    for pat in _REDACT_PATTERNS:
        out = pat.sub("••••••••", out)
    return out
