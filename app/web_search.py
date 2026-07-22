"""Live web search for cybersecurity research (multi-source, parallel, detailed)."""

from __future__ import annotations

import asyncio
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
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_META_DESC_RE = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
    re.I,
)
_META_DESC_RE2 = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
    re.I,
)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 HackGPT/1.4"
)

_SNIPPET_LEN = 900
_DETAIL_LEN = 1600


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
        "assessment", "nuclei", "advisory",
    )
    if not any(t in lower for t in cyber_terms) and not _CVE_RE.search(q):
        queries.append(f"{q} cybersecurity vulnerability OR exploit OR CVE")
    cves = _CVE_RE.findall(q)
    for cve in cves[:2]:
        queries.append(f"{cve} NVD")
        queries.append(f"{cve} exploit PoC")
    seen: set[str] = set()
    out: list[str] = []
    for item in queries:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out[:3]


def _nvd_metrics(cve: dict[str, Any]) -> dict[str, str]:
    metrics = cve.get("metrics") or {}
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        arr = metrics.get(key) or []
        if not arr:
            continue
        data = arr[0].get("cvssData") or {}
        score = data.get("baseScore")
        sev = data.get("baseSeverity") or arr[0].get("baseSeverity") or ""
        vector = data.get("vectorString") or ""
        return {
            "cvss": str(score) if score is not None else "",
            "severity": str(sev),
            "vector": str(vector),
            "cvss_version": key.replace("cvssMetric", ""),
        }
    return {}


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
            out.append({"title": title, "url": link, "snippet": snippet[:_SNIPPET_LEN], "source": "searxng"})
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
            snippet = _clean(sn.group("snippet"))
        if title and href.startswith("http"):
            out.append(
                {
                    "title": title,
                    "url": href,
                    "snippet": snippet[:_SNIPPET_LEN],
                    "source": "duckduckgo",
                }
            )
        if len(out) >= max_results:
            break
    return out


async def _search_duckduckgo_lite(client: httpx.AsyncClient, query: str, max_results: int) -> list[dict[str, str]]:
    headers = {"User-Agent": _UA}
    r = await client.get(
        f"https://lite.duckduckgo.com/lite/?q={quote_plus(query)}",
        headers=headers,
    )
    if r.status_code != 200:
        return []
    out: list[dict[str, str]] = []
    for m in _LITE_LINK_RE.finditer(r.text):
        href = m.group("href")
        title = _clean(m.group("title"))
        if "duckduckgo.com" in href:
            continue
        if title and href.startswith("http"):
            out.append({"title": title, "url": href, "snippet": "", "source": "duckduckgo-lite"})
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
    abstract = (data.get("AbstractText") or "").strip()
    abs_url = (data.get("AbstractURL") or "").strip()
    heading = (data.get("Heading") or query).strip()
    if abstract and abs_url:
        out.append(
            {
                "title": f"{heading} — DuckDuckGo Instant",
                "url": abs_url,
                "snippet": abstract[:_SNIPPET_LEN],
                "source": "duckduckgo-instant",
            }
        )
    for topic in (data.get("RelatedTopics") or [])[:4]:
        if isinstance(topic, dict) and topic.get("Text") and topic.get("FirstURL"):
            out.append(
                {
                    "title": _clean(topic["Text"])[:120],
                    "url": topic["FirstURL"],
                    "snippet": _clean(topic["Text"])[:_SNIPPET_LEN],
                    "source": "duckduckgo-instant",
                }
            )
        elif isinstance(topic, dict) and topic.get("Topics"):
            for sub in topic["Topics"][:2]:
                if sub.get("Text") and sub.get("FirstURL"):
                    out.append(
                        {
                            "title": _clean(sub["Text"])[:120],
                            "url": sub["FirstURL"],
                            "snippet": _clean(sub["Text"])[:_SNIPPET_LEN],
                            "source": "duckduckgo-instant",
                        }
                    )
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
        metrics = _nvd_metrics(cve)
        weaknesses = []
        for w in cve.get("weaknesses") or []:
            for d in w.get("description") or []:
                if d.get("value"):
                    weaknesses.append(d["value"])
        published = (cve.get("published") or "")[:10]
        modified = (cve.get("lastModified") or "")[:10]
        detail_parts = [desc[:800] if desc else ""]
        if metrics.get("cvss"):
            detail_parts.append(
                f"CVSS{metrics.get('cvss_version', '')} {metrics['cvss']} "
                f"({metrics.get('severity', '')}) {metrics.get('vector', '')}".strip()
            )
        if weaknesses:
            detail_parts.append("CWE: " + ", ".join(weaknesses[:4]))
        if published:
            detail_parts.append(f"Published: {published}; Modified: {modified}")
        snippet = " | ".join(p for p in detail_parts if p)[:_DETAIL_LEN]
        out.append(
            {
                "title": f"{cve_id} — NVD {metrics.get('severity', '')}".strip(),
                "url": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                "snippet": snippet,
                "source": "nvd",
                "cvss": metrics.get("cvss", ""),
                "severity": metrics.get("severity", ""),
                "published": published,
            }
        )
    return out


async def _fetch_page_detail(client: httpx.AsyncClient, url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
        if any(x in host for x in ("facebook.com", "twitter.com", "x.com", "youtube.com")):
            return ""
        r = await client.get(url, headers={"User-Agent": _UA, "Accept": "text/html"})
        if r.status_code != 200 or "text/html" not in (r.headers.get("content-type") or ""):
            return ""
        body = r.text[:120_000]
        meta = ""
        m = _META_DESC_RE.search(body) or _META_DESC_RE2.search(body)
        if m:
            meta = _clean(m.group(1))
        # Prefer main-ish text: strip scripts/styles roughly
        stripped = re.sub(r"(?is)<(script|style|nav|footer)[^>]*>.*?</\1>", " ", body)
        text = _clean(stripped)
        # Drop very short chrome
        if len(text) < 80 and not meta:
            return ""
        combined = (meta + " — " if meta else "") + text
        return combined[:_DETAIL_LEN]
    except Exception:
        return ""


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
    """Aggregate SearXNG / DDG / NVD results fast (parallel) with richer detail."""
    limit = max_results or settings.web_search_max_results
    limit = max(1, min(int(limit), 10))
    budget = max(2.0, float(getattr(settings, "web_search_timeout_sec", 5.0)))

    if not settings.web_search_enabled:
        return {"query": query, "results": [], "provider": "disabled", "error": "Web search disabled"}

    queries = _cyber_queries(query)
    if not queries:
        return {"query": query, "results": [], "provider": "none", "error": "Empty query"}

    providers_used: list[str] = []
    buckets: list[list[dict[str, str]]] = []
    error = None

    timeout = httpx.Timeout(connect=2.0, read=min(8.0, budget), write=4.0, pool=4.0)

    async def _run() -> None:
        nonlocal error
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            tasks: list[Any] = []
            labels: list[str] = []

            for cve in _CVE_RE.findall(query)[:2]:
                tasks.append(_search_nvd(client, cve))
                labels.append("nvd")

            primary = queries[0]
            if settings.searxng_url:
                tasks.append(_search_searxng(client, primary, limit))
                labels.append("searxng")
            tasks.append(_search_duckduckgo_html(client, primary, limit))
            labels.append("duckduckgo")
            tasks.append(_search_ddg_instant(client, primary))
            labels.append("duckduckgo-instant")

            # One cyber-biased follow-up max
            if len(queries) > 1:
                tasks.append(_search_duckduckgo_html(client, queries[1], max(3, limit // 2)))
                labels.append("duckduckgo")

            results_list = await asyncio.gather(*tasks, return_exceptions=True)
            for label, res in zip(labels, results_list):
                if isinstance(res, Exception):
                    error = str(res)
                    continue
                if res:
                    buckets.append(res)  # type: ignore[arg-type]
                    providers_used.append(label)

            # Lite fallback only if nothing useful
            merged_preview = _merge_results(*buckets, limit=limit)
            if len(merged_preview) < 2:
                lite = await _search_duckduckgo_lite(client, primary, limit)
                if lite:
                    buckets.append(lite)
                    providers_used.append("duckduckgo-lite")

            merged = _merge_results(*buckets, limit=limit)

            # Fetch page detail for top non-NVD hits (parallel, capped)
            enrich_targets = [item for item in merged if item.get("source") != "nvd"][:3]
            if enrich_targets:
                details = await asyncio.gather(
                    *[_fetch_page_detail(client, item["url"]) for item in enrich_targets],
                    return_exceptions=True,
                )
                for item, detail in zip(enrich_targets, details):
                    if isinstance(detail, str) and detail:
                        if item.get("snippet"):
                            item["detail"] = detail
                            if len(item["snippet"]) < 200:
                                item["snippet"] = (item["snippet"] + " — " + detail)[:_DETAIL_LEN]
                        else:
                            item["snippet"] = detail
                            item["detail"] = detail

    try:
        await asyncio.wait_for(_run(), timeout=budget)
    except asyncio.TimeoutError:
        error = error or f"Search budget {budget:.0f}s reached"
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
        "## Live web search results (detailed cybersecurity)",
        f"Provider: `{payload.get('provider')}` · Query: `{payload.get('query', '')}`",
        "Ground answers in these sources. Cite titles/URLs. Prefer CVSS/CWE/dates when present.",
        "Still give complete technical steps for authorized lab/research use.",
        "",
    ]
    for i, item in enumerate(results, 1):
        lines.append(f"{i}. **{item.get('title', 'Result')}**")
        lines.append(f"   URL: {item.get('url', '')}")
        meta_bits = []
        if item.get("cvss"):
            meta_bits.append(f"CVSS {item['cvss']}")
        if item.get("severity"):
            meta_bits.append(item["severity"])
        if item.get("published"):
            meta_bits.append(f"published {item['published']}")
        if item.get("source"):
            meta_bits.append(item["source"])
        if meta_bits:
            lines.append(f"   Meta: {', '.join(meta_bits)}")
        if item.get("snippet"):
            lines.append(f"   Summary: {item['snippet']}")
        if item.get("detail") and item.get("detail") != item.get("snippet"):
            lines.append(f"   Detail: {item['detail'][:1200]}")
        lines.append("")
    return "\n".join(lines)
