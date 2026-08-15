"""STIX 2.1 ingest/export + TAXII 2.1 collection poll (stdlib + httpx).

No taxii2-client dependency — TAXII is thin HTTP over JSON. This is the
highest-leverage intel path: one parser covers MISP/ISAC/government feeds
instead of N bespoke connectors.

Honest limits: STIX 2.1 bundles only (not 1.x XML); TAXII poll is pull-based
(no long-poll/SSE channel yet); object coverage focuses on indicator,
vulnerability, malware, threat-actor, campaign, and identity.
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from app.config import settings
from app.ops import add_intel_watch, list_intel_watch

_STIX_INDICATOR = "indicator"
_STIX_VULN = "vulnerability"
_STIX_MALWARE = "malware"
_STIX_ACTOR = "threat-actor"
_STIX_CAMPAIGN = "campaign"
_STIX_IDENTITY = "identity"


def parse_stix_bundle(bundle: dict[str, Any] | list) -> dict[str, Any]:
    """Normalize a STIX 2.1 bundle (or list of objects) into SecuraIQ rows."""
    if isinstance(bundle, list):
        objects = bundle
        bundle_id = ""
    else:
        objects = bundle.get("objects") or []
        bundle_id = bundle.get("id") or ""

    indicators: list[dict[str, Any]] = []
    vulns: list[dict[str, Any]] = []
    other: list[dict[str, Any]] = []

    for obj in objects:
        if not isinstance(obj, dict):
            continue
        typ = (obj.get("type") or "").lower()
        if typ == _STIX_INDICATOR:
            pattern = obj.get("pattern") or ""
            name = obj.get("name") or obj.get("id") or "indicator"
            kind, value = _pattern_to_ioc(pattern)
            indicators.append(
                {
                    "stix_id": obj.get("id"),
                    "kind": kind,
                    "value": value or name,
                    "name": name,
                    "pattern": pattern,
                    "labels": obj.get("labels") or [],
                    "confidence": obj.get("confidence"),
                    "raw": obj,
                }
            )
        elif typ == _STIX_VULN:
            name = obj.get("name") or ""
            cve = name if name.upper().startswith("CVE-") else ""
            for ext in obj.get("external_references") or []:
                if (ext.get("source_name") or "").lower() in {"cve", "nvd"} and ext.get("external_id"):
                    cve = ext["external_id"]
            vulns.append(
                {
                    "stix_id": obj.get("id"),
                    "cve": cve,
                    "title": name or cve or "STIX vulnerability",
                    "description": (obj.get("description") or "")[:2000],
                    "raw": obj,
                }
            )
        elif typ in {_STIX_MALWARE, _STIX_ACTOR, _STIX_CAMPAIGN, _STIX_IDENTITY}:
            other.append(
                {
                    "stix_id": obj.get("id"),
                    "type": typ,
                    "name": obj.get("name") or obj.get("id"),
                    "labels": obj.get("labels") or [],
                    "raw": obj,
                }
            )

    return {
        "bundle_id": bundle_id,
        "indicators": indicators,
        "vulnerabilities": vulns,
        "objects": other,
        "counts": {
            "indicators": len(indicators),
            "vulnerabilities": len(vulns),
            "other": len(other),
            "total_objects": len(objects),
        },
    }


def _pattern_to_ioc(pattern: str) -> tuple[str, str]:
    """Best-effort extract from STIX patterning language snippets."""
    p = pattern or ""
    # [ipv4-addr:value = '1.2.3.4']
    import re

    m = re.search(r"ipv4-addr:value\s*=\s*'([^']+)'", p, re.I)
    if m:
        return "ip", m.group(1)
    m = re.search(r"ipv6-addr:value\s*=\s*'([^']+)'", p, re.I)
    if m:
        return "ip", m.group(1)
    m = re.search(r"domain-name:value\s*=\s*'([^']+)'", p, re.I)
    if m:
        return "domain", m.group(1)
    m = re.search(r"url:value\s*=\s*'([^']+)'", p, re.I)
    if m:
        return "url", m.group(1)
    m = re.search(r"file:hashes\.'?(SHA-256|MD5|SHA-1)'?\s*=\s*'([^']+)'", p, re.I)
    if m:
        return "hash", m.group(2)
    m = re.search(r"email-addr:value\s*=\s*'([^']+)'", p, re.I)
    if m:
        return "email", m.group(1)
    # Fallback: first quoted string
    m = re.search(r"'([^']{3,})'", p)
    if m:
        return "ioc", m.group(1)
    return "stix", (p[:120] or "indicator")


def ingest_stix_bundle(user_id: str, bundle: dict[str, Any] | list, *, also_vulns: bool = True) -> dict[str, Any]:
    """Parse STIX and write indicators to intel watch (+ optional vuln rows for CVEs)."""
    parsed = parse_stix_bundle(bundle)
    watched = []
    for ind in parsed["indicators"]:
        value = (ind.get("value") or "").strip()
        if not value:
            continue
        notes = f"stix:{ind.get('stix_id') or ''} {ind.get('name') or ''}".strip()[:400]
        row = add_intel_watch(user_id, kind=ind.get("kind") or "ioc", value=value[:200], notes=notes)
        watched.append(row)

    vulns_created = []
    if also_vulns and parsed["vulnerabilities"]:
        from app.enterprise import create_vulnerability

        for v in parsed["vulnerabilities"][:50]:
            if not (v.get("cve") or v.get("title")):
                continue
            vulns_created.append(
                create_vulnerability(
                    user_id,
                    {
                        "title": v.get("title") or v.get("cve"),
                        "cve": v.get("cve") or "",
                        "severity": "high",
                        "asset_name": "",
                        "source": "stix",
                        "raw_json": json.dumps({"stix_id": v.get("stix_id")}),
                    },
                )
            )

    try:
        from app.realtime_bus import publish

        publish(
            type="intel",
            source="stix",
            indicators=len(watched),
            vulns=len(vulns_created),
            user_id=user_id,
        )
    except Exception:
        pass

    return {
        "ok": True,
        "bundle_id": parsed.get("bundle_id"),
        "counts": parsed["counts"],
        "watch_added": len(watched),
        "vulns_added": len(vulns_created),
        "other_objects": parsed["objects"][:20],
    }


def export_stix_bundle(user_id: str) -> dict[str, Any]:
    """Export intel watchlist (+ optional recent CVE watches) as a STIX 2.1 bundle."""
    objects: list[dict[str, Any]] = []
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for w in list_intel_watch(user_id):
        kind = (w.get("kind") or "ioc").lower()
        value = w.get("value") or ""
        pattern = _ioc_to_pattern(kind, value)
        if not pattern:
            continue
        objects.append(
            {
                "type": "indicator",
                "spec_version": "2.1",
                "id": f"indicator--{w['id']}",
                "created": ts,
                "modified": ts,
                "name": value,
                "description": w.get("notes") or "",
                "pattern": pattern,
                "pattern_type": "stix",
                "valid_from": ts,
                "labels": ["securaiq-watchlist"],
            }
        )
    return {
        "type": "bundle",
        "id": f"bundle--securaiq-{int(time.time())}",
        "objects": objects,
    }


def _ioc_to_pattern(kind: str, value: str) -> str:
    v = value.replace("'", "\\'")
    if kind in {"ip", "ipv4"}:
        return f"[ipv4-addr:value = '{v}']"
    if kind == "domain":
        return f"[domain-name:value = '{v}']"
    if kind == "url":
        return f"[url:value = '{v}']"
    if kind == "email":
        return f"[email-addr:value = '{v}']"
    if kind == "hash":
        algo = "SHA-256" if len(value) == 64 else ("MD5" if len(value) == 32 else "SHA-1")
        return f"[file:hashes.'{algo}' = '{v}']"
    if kind == "cve" or value.upper().startswith("CVE-"):
        return f"[vulnerability:name = '{v}']"
    return f"[x-securaiq-ioc:value = '{v}']"


async def taxii_poll_collection(
    *,
    collection_url: str | None = None,
    api_root: str | None = None,
    collection_id: str | None = None,
    username: str = "",
    password: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    """Pull objects from a TAXII 2.1 collection (GET .../objects/)."""
    url = (collection_url or "").strip()
    if not url:
        root = (api_root or getattr(settings, "taxii_api_root", "") or "").rstrip("/")
        cid = (collection_id or getattr(settings, "taxii_collection_id", "") or "").strip()
        if not root or not cid:
            return {
                "ok": False,
                "error": "not_configured",
                "hint": "Set TAXII_API_ROOT + TAXII_COLLECTION_ID or pass collection_url",
            }
        url = f"{root}/collections/{cid}/objects/"

    auth = None
    user = username or getattr(settings, "taxii_username", "") or ""
    pwd = password or getattr(settings, "taxii_password", "") or ""
    if user:
        auth = (user, pwd)

    headers = {
        "Accept": "application/taxii+json;version=2.1",
        "Content-Type": "application/taxii+json;version=2.1",
    }
    params = {"limit": max(1, min(limit, 500))}
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(url, headers=headers, params=params, auth=auth)
        if resp.status_code >= 400:
            return {
                "ok": False,
                "error": f"taxii_http_{resp.status_code}",
                "detail": resp.text[:500],
                "url": url,
            }
        data = resp.json()
    objects = data.get("objects") or data.get("Objects") or []
    return {
        "ok": True,
        "url": url,
        "object_count": len(objects),
        "bundle": {"type": "bundle", "id": f"bundle--taxii-{int(time.time())}", "objects": objects},
        "more": data.get("more"),
        "next": data.get("next"),
    }


async def taxii_poll_and_ingest(user_id: str, **kwargs: Any) -> dict[str, Any]:
    polled = await taxii_poll_collection(**kwargs)
    if not polled.get("ok"):
        return polled
    ingested = ingest_stix_bundle(user_id, polled["bundle"], also_vulns=True)
    return {"ok": True, "taxii": {"url": polled.get("url"), "object_count": polled.get("object_count")}, "ingest": ingested}
