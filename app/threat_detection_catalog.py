"""Awesome Threat Detection catalog (0x4D31) for SecuraIQ Intel.

Source: https://github.com/0x4d31/awesome-threat-detection
Fetches the upstream README, parses markdown link entries into a searchable
catalog for blue-team / hunt workflows. Cached in-process (+ optional SQLite
via intel_feed_cache) so Live UI refreshes stay cheap.
"""

from __future__ import annotations

import re
import time
from typing import Any

import httpx

from app.intel_feeds import _cache_get, _cache_put

_README_URL = (
    "https://raw.githubusercontent.com/0x4d31/awesome-threat-detection/master/README.md"
)
_SOURCE = "https://github.com/0x4d31/awesome-threat-detection"
_CACHE_FEED = "awesome_threat_detection"
_CACHE_KEY = "readme_v1"
_CACHE_TTL_SEC = 12 * 3600

_HEADING_RE = re.compile(r"^(#{2,3})\s+(.+)$")
_ITEM_RE = re.compile(
    r"^\s*[-*]\s+\[([^\]]+)\]\(([^)]+)\)(?:\s*[—\-–:]\s*(.+))?$"
)

# In-process memo so concurrent SSE/UI polls don't re-parse.
_mem: dict[str, Any] = {"ts": 0.0, "items": [], "categories": []}


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:80] or "misc"


def parse_awesome_readme(md: str) -> list[dict[str, Any]]:
    """Parse markdown list entries under ## / ### headings."""
    category = "General"
    subcategory = ""
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw in (md or "").splitlines():
        line = raw.rstrip()
        hm = _HEADING_RE.match(line)
        if hm:
            level, title = hm.group(1), hm.group(2).strip()
            # Drop emoji prefixes for cleaner UI labels
            title = re.sub(r"^[\W_]+", "", title).strip() or title
            if level == "##":
                category = title
                subcategory = ""
            else:
                subcategory = title
            continue
        im = _ITEM_RE.match(line)
        if not im:
            continue
        name, url, desc = im.group(1).strip(), im.group(2).strip(), (im.group(3) or "").strip()
        if not name or not url or url.startswith("#"):
            continue
        key = f"{name.lower()}|{url.lower()}"
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "id": _slug(f"{category}-{name}")[:100],
                "name": name,
                "url": url,
                "description": desc[:500],
                "category": category,
                "subcategory": subcategory or None,
            }
        )
    return items


async def _fetch_readme() -> str:
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        resp = await client.get(
            _README_URL,
            headers={"User-Agent": "SecuraIQ/1.5 (authorized threat-detection catalog)"},
        )
    if resp.status_code >= 400:
        raise ValueError(f"GitHub README fetch failed: HTTP {resp.status_code}")
    return resp.text or ""


async def load_catalog(*, force: bool = False) -> dict[str, Any]:
    """Return parsed catalog; prefer memory → SQLite cache → live GitHub fetch."""
    now = time.time()
    if not force and _mem["items"] and now - float(_mem["ts"] or 0) < 600:
        return _pack(_mem["items"], cached=True, source="memory")

    if not force:
        payload = _cache_get(_CACHE_FEED, _CACHE_KEY, max_age_sec=_CACHE_TTL_SEC)
        if payload and isinstance(payload, dict):
            items = payload.get("items") or []
            if items:
                _mem.update(ts=now, items=items)
                return _pack(items, cached=True, source="disk")

    md = await _fetch_readme()
    items = parse_awesome_readme(md)
    if not items:
        raise ValueError("Parsed zero catalog entries from awesome-threat-detection README")
    try:
        _cache_put(_CACHE_FEED, _CACHE_KEY, {"items": items, "source": _SOURCE})
    except Exception:
        pass
    _mem.update(ts=now, items=items)
    return _pack(items, cached=False, source="github")


def _pack(
    items: list[dict[str, Any]],
    *,
    cached: bool,
    source: str,
    age_sec: int | None = None,
) -> dict[str, Any]:
    cats: dict[str, int] = {}
    for it in items:
        cats[it["category"]] = cats.get(it["category"], 0) + 1
    return {
        "ok": True,
        "source": _SOURCE,
        "readme": _README_URL,
        "fetched_from": source,
        "cached": cached,
        "age_sec": age_sec,
        "total": len(items),
        "categories": [
            {"name": name, "count": count}
            for name, count in sorted(cats.items(), key=lambda x: (-x[1], x[0]))
        ],
        "items": items,
    }


def search_catalog(
    catalog: dict[str, Any],
    *,
    q: str = "",
    category: str = "",
    limit: int = 80,
) -> dict[str, Any]:
    items = list(catalog.get("items") or [])
    cat = (category or "").strip().lower()
    query = (q or "").strip().lower()
    if cat:
        items = [
            i
            for i in items
            if cat in (i.get("category") or "").lower()
            or cat in (i.get("subcategory") or "").lower()
        ]
    if query:
        items = [
            i
            for i in items
            if query in (i.get("name") or "").lower()
            or query in (i.get("description") or "").lower()
            or query in (i.get("category") or "").lower()
            or query in (i.get("url") or "").lower()
        ]
    limit = max(1, min(int(limit or 80), 300))
    out = {**catalog, "items": items[:limit], "matched": len(items), "q": q or None, "category": category or None}
    out["total_matched"] = len(items)
    return out
