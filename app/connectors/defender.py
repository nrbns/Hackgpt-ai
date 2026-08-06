"""Microsoft Defender for Endpoint connector — alerts + missing-patch data.

Setup (Entra ID > App registrations):
  1. Register an app, grant Application permission `AdvancedQuery.Read.All`
     (or at minimum `Alert.Read.All` + `SecurityRecommendation.Read.All`) on
     the "WindowsDefenderATP" API, and admin-consent it.
  2. Set DEFENDER_TENANT_ID / DEFENDER_CLIENT_ID / DEFENDER_CLIENT_SECRET.

Auth flow (OAuth2 client credentials against Entra ID):
  POST https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token
  -> GET https://api.securitycenter.microsoft.com/api/alerts
  -> GET https://api.securitycenter.microsoft.com/api/machines/SoftwareVulnerabilitiesByMachine
     (Threat & Vulnerability Management — this is the missing-patch / patch-compliance feed)
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import settings

_RESOURCE = "https://api.securitycenter.microsoft.com"
_cache: dict[str, Any] = {"token": None, "expires": 0.0}


def is_configured() -> bool:
    return bool(settings.defender_tenant_id and settings.defender_client_id and settings.defender_client_secret)


async def _access_token(client: httpx.AsyncClient) -> str:
    now = time.time()
    if _cache["token"] and _cache["expires"] > now + 30:
        return _cache["token"]
    resp = await client.post(
        f"https://login.microsoftonline.com/{settings.defender_tenant_id}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": settings.defender_client_id,
            "client_secret": settings.defender_client_secret,
            "scope": f"{_RESOURCE}/.default",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.status_code >= 400:
        raise ValueError(f"Defender token error {resp.status_code}: {resp.text[:300]}")
    tok = resp.json()
    _cache.update(token=tok["access_token"], expires=now + int(tok.get("expires_in", 3300)))
    return _cache["token"]


def _normalize_severity(sev: str) -> str:
    return {"high": "critical", "medium": "high", "low": "medium", "informational": "low"}.get(
        (sev or "").lower(), "medium"
    )


async def fetch_detections(limit: int = 100) -> list[dict[str, Any]]:
    """Fetch recent Defender for Endpoint alerts, normalized for XDR ingestion."""
    if not is_configured():
        return []
    async with httpx.AsyncClient(timeout=20.0) as client:
        token = await _access_token(client)
        resp = await client.get(
            f"{_RESOURCE}/api/alerts",
            params={"$top": min(limit, 100)},
            headers={"Authorization": f"Bearer {token}"},
        )
    if resp.status_code >= 400:
        raise ValueError(f"Defender alerts error {resp.status_code}: {resp.text[:300]}")
    items = (resp.json() or {}).get("value", [])
    out: list[dict[str, Any]] = []
    for a in items:
        out.append(
            {
                "vendor": "defender",
                "external_id": a.get("id", ""),
                "kind": "malware" if a.get("category") == "Malware" else "detection",
                "severity": _normalize_severity(a.get("severity")),
                "host": a.get("computerDnsName") or "",
                "title": a.get("title") or "Defender alert",
                "description": a.get("description") or "",
                "raw": a,
            }
        )
    return out


async def fetch_missing_patches(limit: int = 200) -> list[dict[str, Any]]:
    """Fetch per-machine missing-software (patch gap) rows from Defender TVM.

    This is the real patch-compliance signal: each row is a specific missing
    security update on a specific managed endpoint, not a generic checklist.
    """
    if not is_configured():
        return []
    async with httpx.AsyncClient(timeout=25.0) as client:
        token = await _access_token(client)
        resp = await client.get(
            f"{_RESOURCE}/api/machines/SoftwareVulnerabilitiesByMachine",
            headers={"Authorization": f"Bearer {token}"},
        )
    if resp.status_code >= 400:
        raise ValueError(f"Defender TVM error {resp.status_code}: {resp.text[:300]}")
    items = (resp.json() or {}).get("value", [])
    out: list[dict[str, Any]] = []
    for row in items[:limit]:
        out.append(
            {
                "vendor": "defender",
                "external_id": f"{row.get('deviceId', '')}:{row.get('cveId', '')}",
                "kind": "patch_missing",
                "severity": _normalize_severity(row.get("severity") or row.get("vulnerabilitySeverityLevel")),
                "host": row.get("deviceName") or row.get("deviceId") or "",
                "title": f"{row.get('cveId', 'Unknown CVE')} — {row.get('softwareName', 'unknown software')}",
                "description": f"vendor={row.get('softwareVendor')} version={row.get('softwareVersion')}",
                "raw": row,
            }
        )
    return out
