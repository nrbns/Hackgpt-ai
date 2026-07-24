"""Threat intel feeds: CISA KEV (primary) + NVD CVE lookup (ToS-aware, rate-limited)."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.db import audit, get_conn, new_id, now, row_to_dict
from app.ops import add_intel_watch, list_intel_watch

KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
NVD_CVE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"


def ensure_intel_cache_schema() -> None:
    c = get_conn()
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS intel_feed_cache (
            id TEXT PRIMARY KEY,
            feed TEXT NOT NULL,
            key TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            fetched_at REAL NOT NULL,
            UNIQUE(feed, key)
        );
        """
    )
    c.commit()


def _cache_put(feed: str, key: str, payload: dict[str, Any]) -> None:
    ensure_intel_cache_schema()
    c = get_conn()
    existing = c.execute(
        "SELECT id FROM intel_feed_cache WHERE feed = ? AND key = ?", (feed, key)
    ).fetchone()
    if existing:
        c.execute(
            "UPDATE intel_feed_cache SET payload_json = ?, fetched_at = ? WHERE id = ?",
            (json.dumps(payload), now(), existing["id"]),
        )
    else:
        c.execute(
            "INSERT INTO intel_feed_cache (id, feed, key, payload_json, fetched_at) VALUES (?, ?, ?, ?, ?)",
            (new_id(), feed, key, json.dumps(payload), now()),
        )
    c.commit()


def _cache_get(feed: str, key: str, max_age_sec: float = 86400) -> dict[str, Any] | None:
    ensure_intel_cache_schema()
    row = get_conn().execute(
        "SELECT * FROM intel_feed_cache WHERE feed = ? AND key = ?", (feed, key)
    ).fetchone()
    if not row:
        return None
    if now() - float(row["fetched_at"]) > max_age_sec:
        return None
    try:
        return json.loads(row["payload_json"])
    except json.JSONDecodeError:
        return None


async def fetch_cisa_kev(*, limit: int = 40) -> dict[str, Any]:
    cached = _cache_get("kev", "catalog", max_age_sec=43200)
    if cached:
        vulns = (cached.get("vulnerabilities") or [])[:limit]
        return {"source": "cisa_kev", "cached": True, "count": len(vulns), "items": vulns}

    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
        r = await client.get(KEV_URL)
        r.raise_for_status()
        data = r.json()
    _cache_put("kev", "catalog", data)
    vulns = (data.get("vulnerabilities") or [])[:limit]
    # newest first if dates present
    vulns = sorted(vulns, key=lambda x: x.get("dateAdded") or "", reverse=True)[:limit]
    return {
        "source": "cisa_kev",
        "cached": False,
        "catalog_version": data.get("catalogVersion"),
        "count": len(vulns),
        "items": [
            {
                "cve": v.get("cveID"),
                "vendor": v.get("vendorProject"),
                "product": v.get("product"),
                "name": v.get("vulnerabilityName"),
                "date_added": v.get("dateAdded"),
                "ransomware": v.get("knownRansomwareCampaignUse"),
                "notes": (v.get("shortDescription") or "")[:400],
            }
            for v in vulns
        ],
    }


async def lookup_nvd_cve(cve_id: str) -> dict[str, Any]:
    cve = (cve_id or "").strip().upper()
    if not cve.startswith("CVE-"):
        raise ValueError("Provide a CVE-ID (e.g. CVE-2024-1234)")
    cached = _cache_get("nvd", cve, max_age_sec=604800)
    if cached:
        return {"source": "nvd", "cached": True, **cached}

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        r = await client.get(NVD_CVE_URL, params={"cveId": cve})
        if r.status_code == 404:
            raise ValueError("CVE not found in NVD")
        r.raise_for_status()
        data = r.json()

    items = data.get("vulnerabilities") or []
    if not items:
        raise ValueError("CVE not found in NVD")
    cve_obj = items[0].get("cve") or {}
    metrics = cve_obj.get("metrics") or {}
    cvss = None
    severity = None
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        arr = metrics.get(key) or []
        if arr:
            cvss_data = (arr[0].get("cvssData") or {})
            cvss = cvss_data.get("baseScore")
            severity = cvss_data.get("baseSeverity") or arr[0].get("baseSeverity")
            break
    descs = cve_obj.get("descriptions") or []
    desc = next((d.get("value") for d in descs if d.get("lang") == "en"), "") or (
        descs[0].get("value") if descs else ""
    )
    out = {
        "cve": cve,
        "cvss": cvss,
        "severity": severity,
        "description": (desc or "")[:1200],
        "published": cve_obj.get("published"),
        "last_modified": cve_obj.get("lastModified"),
    }
    _cache_put("nvd", cve, out)
    return {"source": "nvd", "cached": False, **out}


async def sync_kev_to_watchlist(user_id: str, *, limit: int = 25) -> dict[str, Any]:
    """Add newest KEV CVEs to the user's watchlist (skip duplicates)."""
    feed = await fetch_cisa_kev(limit=limit)
    existing = {(w.get("value") or "").upper() for w in list_intel_watch(user_id)}
    added = 0
    for item in feed.get("items") or []:
        cve = (item.get("cve") or "").upper()
        if not cve or cve in existing:
            continue
        notes = f"CISA KEV · {item.get('vendor')} {item.get('product')} · {item.get('name')}"[:400]
        add_intel_watch(user_id, kind="kev", value=cve, notes=notes)
        existing.add(cve)
        added += 1
    audit("intel_kev_sync", user_id, {"added": added, "limit": limit})
    return {"ok": True, "added": added, "feed_count": feed.get("count"), "cached": feed.get("cached")}
