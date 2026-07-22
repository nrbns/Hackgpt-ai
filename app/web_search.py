"""Live web search for cybersecurity research (multi-source)."""

from __future__ import annotations

import html as html_lib
import re
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx

from app.config import settings

_TAG_RE = re.compile(r"<[^>]+>")
_CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)

_RESULT_RE = re.compile(
    r'class="result__a"[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_SNIPPET_AFTER_RE = re.compile(
    r'class="result__snippet"[^>]*>(?P<snippet>.*?)</(?:a|td|div)',
    re.IGNORECASE | re.DOTALL,
)
_LITE_LINK_RE = re.compile(
    r'<a[^>]+href="(?P<href>https?://[^"]+)"[^>]*>(?P<title>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 HackGPT/1.3"
)


def _clean(text: str) -> str:
    text = html_lib.unescape(_TAG_RE.sub("", text or ""))
    return re.sub(r"\s+", " ", text).strip()


def _unwrap_ddg(href: str) -> str:
    href = html_lib.unescape(href)
    if "uddg=" in href:
        qs = parse_qs(urlparse(href).query)
        if qs.get("uddg"):
            return unquote(qs["uddg"][0])
    return href


def _cyber_queries(query: str) -> list[str]:
    """Build primary + cyber-biased follow-up queries."""
    q = (query or "").strip()
    if not q:
        return []
    queries = [q]
    lower = q.lower()
    cyber_terms = (
        "cve", "exploit", "pentest", "owasp", "nmap", "kerberos", "xss", "sqli",
        "ransomware", "malware", "yara", "att&ck", "mitre", "vulnerability",
    )
    if not any(t in lower for t in cyber_terms) and not _CVE_RE.search(q):
        queries.append(f"{q} cybersecurity vulnerability OR exploit OR CVE")
    cves = _CVE_RE.findall(q)
    for cve in cves[:2]:
        queries.append(f"{cve} NVD")
        queries.append(f"{cve} exploit")
    # de-dupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for item in queries:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out[:4]


async def _search_searxng(client: httpx.AsyncClient, query: str, max_results: int) -> list[dict[str, str]]:
    base = (settings.searxng_url or "").rstrip("/")
    if not base:
        return []
    r = await client.get(
        f"{base}/search",
        params={"q": query, "format": "json", "categories": "general"},
    )
    if r.status_code != 200:
        return []
    data = r.json()
    out: list[dict[str, str]] = []
    for item in data.get("results", [])[:max_results]:
        title = (item.get("title") or "").strip()
        link = (item.get("url") or "").strip()
        snippet = (item.get("content") or item.get("snippet") or "").strip()
        if title and link:
            out.append({"title": title, "url": link, "snippet": snippet[:420]})
    return out


async def _search_duckduckgo_html(client: httpx.AsyncClient, query: str, max_results: int) -> list[dict[str, str]]:
    headers = {"User-Agent": _UA, "Accept": "text/html"}
    r = await client.post(
        "https://html.duckduckgo.com/html/",
        data={"q": query},
        headers=headers,
    )
    if r.status_code != 200:
        r = await client.get(
            f"https://html.duckduckgo.com/html/?q={quote_plus(query)}",
            headers=headers,
        )
    if r.status_code != 200:
        return []
    body = r.text
    out: list[dict[str, str]] = []
    for m in _RESULT_RE.finditer(body):
        title = _clean(m.group("title"))
        href = _unwrap_ddg(m.group("href"))
        snippet = ""
        sn = _SNIPPET_AFTER_RE.search(body, m.end())
        if sn:
            snippet = _clean(sn.group("snippet"))[:420]
        if title and href.startswith("http"):
            out.append({"title": title, "url": href, "snippet": snippet})
        if len(out) >= max_results:
            break
    return out


async def _search_duckduckgo_lite(client: httpx.AsyncClient, query: str, max_results: int) -> list[dict[str, str]]:
    headers = {"User-Agent": _UA, "Accept": "text/html"}
    r = await client.post(
        "https://lite.duckduckgo.com/lite/",
        data={"q": query},
        headers=headers,
    )
    if r.status_code != 200:
        return []
    out: list[dict[str, str]] = []
    for m in _LITE_LINK_RE.finditer(r.text):
        href = _unwrap_ddg(m.group("href"))
        title = _clean(m.group("title"))
        if not title or not href.startswith("http"):
            continue
        if "duckduckgo.com" in href:
            continue
        out.append({"title": title, "url": href, "snippet": ""})
        if len(out) >= max_results:
            break
    return out


async def _search_ddg_instant(client: httpx.AsyncClient, query: str) -> list[dict[str, str]]:
    r = await client.get(
        "https://api.duckduckgo.com/",
        params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
        headers={"User-Agent": _UA},
    )
    if r.status_code != 200:
        return []
    data = r.json()
    out: list[dict[str, str]] = []
    if data.get("AbstractText") and data.get("AbstractURL"):
        out.append(
            {
                "title": data.get("Heading") or query,
                "url": data["AbstractURL"],
                "snippet": data["AbstractText"][:420],
            }
        )
    for topic in data.get("RelatedTopics") or []:
        if isinstance(topic, dict) and topic.get("FirstURL") and topic.get("Text"):
            out.append(
                {
                    "title": topic["Text"][:80],
                    "url": topic["FirstURL"],
                    "snippet": topic["Text"][:420],
                }
            )
        elif isinstance(topic, dict) and "Topics" in topic:
            for sub in topic.get("Topics") or []:
                if sub.get("FirstURL") and sub.get("Text"):
                    out.append(
                        {
                            "title": sub["Text"][:80],
                            "url": sub["FirstURL"],
                            "snippet": sub["Text"][:420],
                        }
                    )
        if len(out) >= 5:
            break
    return out


async def _search_nvd(client: httpx.AsyncClient, cve_id: str) -> list[dict[str, str]]:
    cve_id = cve_id.upper()
    r = await client.get(
        "https://services.nvd.nist.gov/rest/json/cves/2.0",
        params={"cveId": cve_id},
        headers={"User-Agent": _UA},
    )
    if r.status_code != 200:
        return []
    data = r.json()
    out: list[dict[str, str]] = []
    for vul in data.get("vulnerabilities") or []:
        cve = vul.get("cve") or {}
        descriptions = cve.get("descriptions") or []
        desc = next((d.get("value") for d in descriptions if d.get("lang") == "en"), "")
        out.append(
            {
                "title": f"{cve_id} — NVD",
                "url": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                "snippet": (desc or "")[:420],
            }
        )
    return out


def _merge_results(*groups: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for group in groups:
        for item in group:
            url = (item.get("url") or "").split("#")[0].rstrip("/")
            if not url or url in seen:
                continue
            seen.add(url)
            out.append(item)
            if len(out) >= limit:
                return out
    return out


async def web_search(query: str, max_results: int | None = None) -> dict[str, Any]:
    """Aggregate SearXNG / DDG / NVD results for cybersecurity queries."""
    limit = max_results or settings.web_search_max_results
    limit = max(1, min(int(limit), 10))

    if not settings.web_search_enabled:
        return {"query": query, "results": [], "provider": "disabled", "error": "Web search disabled"}

    queries = _cyber_queries(query)
    providers_used: list[str] = []
    buckets: list[list[dict[str, str]]] = []
    error = None

    timeout = httpx.Timeout(connect=3.0, read=12.0, write=8.0, pool=8.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            # CVE enrichment first
            for cve in _CVE_RE.findall(query)[:2]:
                nvd = await _search_nvd(client, cve)
                if nvd:
                    buckets.append(nvd)
                    providers_used.append("nvd")

            for q in queries:
                if settings.searxng_url:
                    sx = await _search_searxng(client, q, limit)
                    if sx:
                        buckets.append(sx)
                        providers_used.append("searxng")

                html_hits = await _search_duckduckgo_html(client, q, limit)
                if html_hits:
                    buckets.append(html_hits)
                    providers_used.append("duckduckgo")
                else:
                    lite = await _search_duckduckgo_lite(client, q, limit)
                    if lite:
                        buckets.append(lite)
                        providers_used.append("duckduckgo-lite")

                instant = await _search_ddg_instant(client, q)
                if instant:
                    buckets.append(instant)
                    providers_used.append("duckduckgo-instant")

                # Enough results — stop extra queries
                merged_preview = _merge_results(*buckets, limit=limit)
                if len(merged_preview) >= limit:
                    break
    except Exception as exc:
        error = str(exc)

    results = _merge_results(*buckets, limit=limit)
    provider = "+".join(dict.fromkeys(providers_used)) if providers_used else ("error" if error else "none")

    return {
        "query": query,
        "queries": queries,
        "results": results,
        "provider": provider,
        "error": error if not results else None,
    }


def format_search_context(payload: dict[str, Any]) -> str:
    results = payload.get("results") or []
    if not results:
        err = payload.get("error") or "No live results"
        return (
            "## Live web search\n"
            f"Query: `{payload.get('query', '')}`\n"
            f"No results ({err}). Answer fully from cybersecurity expertise; note live search was empty."
        )

    lines = [
        "## Live web search results (cybersecurity)",
        f"Provider: `{payload.get('provider')}` · Query: `{payload.get('query', '')}`",
        "Ground answers in these sources when relevant. Cite titles/URLs. "
        "Still give complete technical steps for authorized lab/research use.",
        "",
    ]
    for i, item in enumerate(results, 1):
        lines.append(f"{i}. **{item.get('title', 'Result')}**")
        lines.append(f"   URL: {item.get('url', '')}")
        if item.get("snippet"):
            lines.append(f"   Snippet: {item['snippet']}")
        lines.append("")
    return "\n".join(lines)
