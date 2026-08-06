"""CrowdStrike Falcon connector — pulls Detections via the Falcon REST API.

Setup (Falcon console > Support and resources > API Clients and Keys):
  1. Create an OAuth2 API client with the "Detections: Read" scope.
  2. Set CROWDSTRIKE_CLIENT_ID / CROWDSTRIKE_CLIENT_SECRET in Settings/.env.
  3. CROWDSTRIKE_BASE_URL defaults to the US-1 cloud (api.crowdstrike.com) —
     change it for EU-1/US-2/US-GOV-1 tenants (see Falcon API docs).

Auth flow (OAuth2 client credentials):
  POST {base}/oauth2/token
  -> GET  {base}/detects/queries/detects/v1   (recent detection IDs)
  -> POST {base}/detects/entities/summaries/GET/v1   (hydrate IDs to full detections)
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import settings

_cache: dict[str, Any] = {"token": None, "expires": 0.0}


def is_configured() -> bool:
    return bool(settings.crowdstrike_client_id and settings.crowdstrike_client_secret)


async def _access_token(client: httpx.AsyncClient) -> str:
    now = time.time()
    if _cache["token"] and _cache["expires"] > now + 30:
        return _cache["token"]
    base = settings.crowdstrike_base_url.rstrip("/")
    resp = await client.post(
        f"{base}/oauth2/token",
        data={
            "client_id": settings.crowdstrike_client_id,
            "client_secret": settings.crowdstrike_client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.status_code >= 400:
        raise ValueError(f"CrowdStrike token error {resp.status_code}: {resp.text[:300]}")
    tok = resp.json()
    _cache.update(token=tok["access_token"], expires=now + int(tok.get("expires_in", 1700)))
    return _cache["token"]


def _normalize_severity(score: int | None) -> str:
    # Falcon detections carry a 0-100 max_severity score, not a label.
    s = score or 0
    if s >= 80:
        return "critical"
    if s >= 60:
        return "high"
    if s >= 30:
        return "medium"
    return "low"


async def fetch_detections(limit: int = 100) -> list[dict[str, Any]]:
    """Fetch recent CrowdStrike Falcon detections, normalized for XDR ingestion."""
    if not is_configured():
        return []
    base = settings.crowdstrike_base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=20.0) as client:
        token = await _access_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        ids_resp = await client.get(
            f"{base}/detects/queries/detects/v1",
            params={"limit": min(limit, 100), "sort": "first_behavior|desc"},
            headers=headers,
        )
        if ids_resp.status_code >= 400:
            raise ValueError(f"CrowdStrike query error {ids_resp.status_code}: {ids_resp.text[:300]}")
        ids = (ids_resp.json() or {}).get("resources", [])
        if not ids:
            return []
        detail_resp = await client.post(
            f"{base}/detects/entities/summaries/GET/v1",
            json={"ids": ids},
            headers={**headers, "Content-Type": "application/json"},
        )
    if detail_resp.status_code >= 400:
        raise ValueError(f"CrowdStrike summaries error {detail_resp.status_code}: {detail_resp.text[:300]}")
    resources = (detail_resp.json() or {}).get("resources", [])
    out: list[dict[str, Any]] = []
    for d in resources:
        behaviors = d.get("behaviors") or [{}]
        b0 = behaviors[0] if behaviors else {}
        out.append(
            {
                "vendor": "crowdstrike",
                "external_id": d.get("detection_id", ""),
                "kind": "malware" if b0.get("ioc_type") else "detection",
                "severity": _normalize_severity(d.get("max_severity")),
                "host": (d.get("device") or {}).get("hostname") or "",
                "title": b0.get("display_name") or d.get("detection_id") or "CrowdStrike detection",
                "description": b0.get("description") or "",
                "raw": d,
            }
        )
    return out
