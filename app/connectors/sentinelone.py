"""SentinelOne connector — pulls Threats via the Management API.

Setup:
  1. In the SentinelOne console: Settings > Users > Service Users (or your
     account API token) — generate an API token.
  2. Set SENTINELONE_API_TOKEN and SENTINELONE_BASE_URL (e.g.
     https://your-tenant.sentinelone.net) in Settings/.env.

Auth: static bearer-style token in the `Authorization: ApiToken <token>` header
(SentinelOne's own scheme, not standard OAuth2 Bearer) — no token exchange step.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


def is_configured() -> bool:
    return bool(settings.sentinelone_api_token and settings.sentinelone_base_url)


def _normalize_severity(analyst_verdict: str, confidence: str) -> str:
    verdict = (analyst_verdict or "").lower()
    conf = (confidence or "").lower()
    if verdict in ("true_positive", "malicious") or conf == "malicious":
        return "critical"
    if conf == "suspicious":
        return "high"
    if verdict == "undefined":
        return "medium"
    return "low"


async def fetch_detections(limit: int = 100) -> list[dict[str, Any]]:
    """Fetch recent SentinelOne threats, normalized for XDR ingestion."""
    if not is_configured():
        return []
    base = settings.sentinelone_base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(
            f"{base}/web/api/v2.1/threats",
            params={"limit": min(limit, 100), "sortBy": "createdAt", "sortOrder": "desc"},
            headers={"Authorization": f"ApiToken {settings.sentinelone_api_token}"},
        )
    if resp.status_code >= 400:
        raise ValueError(f"SentinelOne error {resp.status_code}: {resp.text[:300]}")
    items = (resp.json() or {}).get("data", [])
    out: list[dict[str, Any]] = []
    for t in items:
        info = t.get("threatInfo") or {}
        agent = t.get("agentRealtimeInfo") or {}
        out.append(
            {
                "vendor": "sentinelone",
                "external_id": t.get("id", ""),
                "kind": "malware",
                "severity": _normalize_severity(info.get("analystVerdict"), info.get("confidenceLevel")),
                "host": agent.get("agentComputerName") or "",
                "title": info.get("threatName") or "SentinelOne threat",
                "description": f"classification={info.get('classification')} verdict={info.get('analystVerdict')}",
                "raw": t,
            }
        )
    return out
