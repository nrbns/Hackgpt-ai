"""Sophos Central connector — pulls Alerts (detections) via the Sophos Central API.

Setup (Sophos Central Admin > Global Settings > API Credentials Management):
  1. Create an API credential (Service Principal) — gives you a Client ID + Client Secret.
  2. Set SOPHOS_CLIENT_ID / SOPHOS_CLIENT_SECRET in Settings/.env.

Auth flow (OAuth2 client credentials, per Sophos's documented API):
  POST https://id.sophos.com/api/v2/oauth2/token
  -> GET https://api.central.sophos.com/whoami/v1   (resolves tenant id + regional API host)
  -> GET {dataRegion}/common/v1/alerts               (X-Tenant-ID header)

No SDK — direct REST, matching the pattern used for the other connectors in this package.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import settings

_TOKEN_URL = "https://id.sophos.com/api/v2/oauth2/token"
_WHOAMI_URL = "https://api.central.sophos.com/whoami/v1"

_cache: dict[str, Any] = {"token": None, "expires": 0.0, "tenant_id": None, "api_host": None}


def is_configured() -> bool:
    return bool(settings.sophos_client_id and settings.sophos_client_secret)


async def _authenticate(client: httpx.AsyncClient) -> tuple[str, str, str]:
    """Returns (access_token, tenant_id, data_region_api_host)."""
    now = time.time()
    if _cache["token"] and _cache["expires"] > now + 30:
        return _cache["token"], _cache["tenant_id"], _cache["api_host"]

    resp = await client.post(
        _TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": settings.sophos_client_id,
            "client_secret": settings.sophos_client_secret,
            "scope": "token",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.status_code >= 400:
        raise ValueError(f"Sophos token error {resp.status_code}: {resp.text[:300]}")
    tok = resp.json()
    access_token = tok["access_token"]

    who = await client.get(_WHOAMI_URL, headers={"Authorization": f"Bearer {access_token}"})
    if who.status_code >= 400:
        raise ValueError(f"Sophos whoami error {who.status_code}: {who.text[:300]}")
    who_data = who.json()
    tenant_id = who_data.get("id", "")
    api_host = (who_data.get("apiHosts") or {}).get("dataRegion") or "https://api-us01.central.sophos.com"

    _cache.update(
        token=access_token,
        expires=now + int(tok.get("expires_in", 3300)),
        tenant_id=tenant_id,
        api_host=api_host,
    )
    return access_token, tenant_id, api_host


def _normalize_severity(sophos_severity: str) -> str:
    return {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}.get(
        (sophos_severity or "").lower(), "medium"
    )


async def fetch_detections(limit: int = 100) -> list[dict[str, Any]]:
    """Fetch recent Sophos Central alerts, normalized for XDR ingestion."""
    if not is_configured():
        return []
    async with httpx.AsyncClient(timeout=20.0) as client:
        token, tenant_id, api_host = await _authenticate(client)
        resp = await client.get(
            f"{api_host}/common/v1/alerts",
            params={"pageSize": min(limit, 100)},
            headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": tenant_id},
        )
    if resp.status_code >= 400:
        raise ValueError(f"Sophos alerts error {resp.status_code}: {resp.text[:300]}")
    items = (resp.json() or {}).get("items", [])
    out: list[dict[str, Any]] = []
    for a in items:
        out.append(
            {
                "vendor": "sophos",
                "external_id": a.get("id", ""),
                "kind": "malware" if "malware" in (a.get("category") or "").lower() else "detection",
                "severity": _normalize_severity(a.get("severity")),
                "host": ((a.get("managedAgent") or {}).get("name")) or "",
                "title": a.get("description") or a.get("type") or "Sophos alert",
                "description": f"category={a.get('category')} type={a.get('type')} product={a.get('product')}",
                "raw": a,
            }
        )
    return out
