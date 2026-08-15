"""Microsoft Defender for Endpoint + Defender XDR advanced hunting.

Setup (Entra ID > App registrations):
  1. Register an app and admin-consent the permissions you need:
       • WindowsDefenderATP / MDE:
           Alert.Read.All, Machine.Read.All (or SecurityRecommendation.Read.All)
       • Advanced hunting (pick one — Graph is preferred):
           Microsoft Graph: ThreatHunting.Read.All
           Microsoft Threat Protection (legacy): AdvancedHunting.Read.All
         See:
           https://learn.microsoft.com/en-us/defender-xdr/api-advanced-hunting
           https://learn.microsoft.com/en-us/graph/api/security-security-runhuntingquery
  2. Set DEFENDER_TENANT_ID / DEFENDER_CLIENT_ID / DEFENDER_CLIENT_SECRET.

Auth (OAuth2 client credentials):
  POST https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token
  Resource scopes (separate tokens):
    • https://api.securitycenter.microsoft.com/.default  — alerts / TVM
    • https://graph.microsoft.com/.default               — Graph runHuntingQuery
    • https://api.security.microsoft.com/.default        — legacy advanced hunting

Hunting endpoints:
  Graph (preferred): POST /v1.0/security/runHuntingQuery
  Legacy (retiring): POST https://api.security.microsoft.com/api/advancedhunting/run

Live alert detections (SOC panel): `app/xdr_stream.py` near-realtime poll of
`fetch_detections` (default 60s). Graph change-notifications / Event Hub export
would need a public webhook or Azure infra — local-first path is the tight poll
plus `POST /api/xdr/ingest`.
"""

from __future__ import annotations

import re
import time
from typing import Any, Literal

import httpx

from app.config import settings

_RESOURCE_MDE = "https://api.securitycenter.microsoft.com"
_RESOURCE_GRAPH = "https://graph.microsoft.com"
_RESOURCE_MTP = "https://api.security.microsoft.com"

# Per-resource token cache: {resource: {"token": str|None, "expires": float}}
_token_cache: dict[str, dict[str, Any]] = {}

HuntingBackend = Literal["auto", "graph", "legacy"]

_MAX_RESULT_ROWS = 200
_MAX_QUERY_CHARS = 8000

DEFAULT_LIVE_QUERY = (
    "DeviceProcessEvents\n"
    "| where Timestamp > ago(1h)\n"
    "| project Timestamp, DeviceName, FileName, FolderPath, "
    "InitiatingProcessFileName, InitiatingProcessCommandLine\n"
    "| order by Timestamp desc\n"
    "| limit 25"
)


def is_configured() -> bool:
    return bool(settings.defender_tenant_id and settings.defender_client_id and settings.defender_client_secret)


def hunting_backend() -> HuntingBackend:
    raw = (getattr(settings, "defender_hunting_api", None) or "auto").strip().lower()
    if raw in ("graph", "legacy", "auto"):
        return raw  # type: ignore[return-value]
    return "auto"


async def _access_token(client: httpx.AsyncClient, resource: str) -> str:
    """Client-credentials token for a specific Microsoft API resource."""
    now = time.time()
    cached = _token_cache.get(resource) or {"token": None, "expires": 0.0}
    if cached.get("token") and float(cached.get("expires") or 0) > now + 30:
        return str(cached["token"])
    resp = await client.post(
        f"https://login.microsoftonline.com/{settings.defender_tenant_id}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": settings.defender_client_id,
            "client_secret": settings.defender_client_secret,
            "scope": f"{resource}/.default",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.status_code >= 400:
        raise ValueError(f"Defender token error ({resource}) {resp.status_code}: {resp.text[:300]}")
    tok = resp.json()
    _token_cache[resource] = {
        "token": tok["access_token"],
        "expires": now + int(tok.get("expires_in", 3300)),
    }
    return str(_token_cache[resource]["token"])


def _normalize_severity(sev: str) -> str:
    return {"high": "critical", "medium": "high", "low": "medium", "informational": "low"}.get(
        (sev or "").lower(), "medium"
    )


async def fetch_detections(limit: int = 100) -> list[dict[str, Any]]:
    """Fetch recent Defender for Endpoint alerts, normalized for XDR ingestion."""
    if not is_configured():
        return []
    async with httpx.AsyncClient(timeout=20.0) as client:
        token = await _access_token(client, _RESOURCE_MDE)
        resp = await client.get(
            f"{_RESOURCE_MDE}/api/alerts",
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
    """Fetch per-machine missing-software (patch gap) rows from Defender TVM."""
    if not is_configured():
        return []
    async with httpx.AsyncClient(timeout=25.0) as client:
        token = await _access_token(client, _RESOURCE_MDE)
        resp = await client.get(
            f"{_RESOURCE_MDE}/api/machines/SoftwareVulnerabilitiesByMachine",
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


def _validate_query(query: str) -> str:
    q = (query or "").strip()
    if not q:
        raise ValueError("KQL Query is required")
    if len(q) > _MAX_QUERY_CHARS:
        raise ValueError(f"Query exceeds {_MAX_QUERY_CHARS} characters")
    banned = re.compile(
        r"\b(drop|delete|alter|insert|update|\.set|\.append|\.delete|"
        r"invoke-command|invoke-expression)\b",
        re.I,
    )
    if banned.search(q):
        raise ValueError("Query rejected: advanced hunting is read-only KQL only")
    return q


def _normalize_hunting_response(
    data: dict[str, Any],
    *,
    backend: str,
    query: str,
    limit: int,
) -> dict[str, Any]:
    """Unify Graph (schema/results) and legacy (Schema/Results/Stats) payloads."""
    schema = data.get("schema") or data.get("Schema") or []
    results = data.get("results") or data.get("Results") or []
    stats = data.get("Stats") or data.get("stats") or {}
    if not isinstance(results, list):
        results = []
    clipped = results[: max(1, min(limit, _MAX_RESULT_ROWS))]
    return {
        "ok": True,
        "backend": backend,
        "query": query,
        "schema": schema,
        "results": clipped,
        "result_count": len(clipped),
        "result_total": len(results),
        "stats": stats if isinstance(stats, dict) else {},
        "live": True,
        "docs": {
            "graph": "https://learn.microsoft.com/en-us/graph/api/security-security-runhuntingquery",
            "legacy": "https://learn.microsoft.com/en-us/defender-xdr/api-advanced-hunting",
        },
    }


async def _run_graph(
    client: httpx.AsyncClient,
    query: str,
    timespan: str | None,
    limit: int,
) -> dict[str, Any]:
    token = await _access_token(client, _RESOURCE_GRAPH)
    body: dict[str, Any] = {"Query": query}
    if timespan:
        body["Timespan"] = timespan
    resp = await client.post(
        f"{_RESOURCE_GRAPH}/v1.0/security/runHuntingQuery",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=180.0,
    )
    if resp.status_code >= 400:
        raise ValueError(f"Graph hunting error {resp.status_code}: {resp.text[:500]}")
    return _normalize_hunting_response(resp.json() or {}, backend="graph", query=query, limit=limit)


async def _run_legacy(
    client: httpx.AsyncClient,
    query: str,
    limit: int,
) -> dict[str, Any]:
    """Legacy MTP advanced hunting — same shape as Icewolf PowerShell samples."""
    token = await _access_token(client, _RESOURCE_MTP)
    resp = await client.post(
        f"{_RESOURCE_MTP}/api/advancedhunting/run",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"Query": query},
        timeout=180.0,
    )
    if resp.status_code >= 400:
        raise ValueError(f"Legacy hunting error {resp.status_code}: {resp.text[:500]}")
    return _normalize_hunting_response(resp.json() or {}, backend="legacy", query=query, limit=limit)


async def run_advanced_hunting(
    query: str,
    *,
    timespan: str | None = None,
    backend: HuntingBackend | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Run KQL advanced hunting against the configured Defender tenant (live only).

    Prefer Graph ``runHuntingQuery``; fall back to legacy MTP. No demo/synthetic data.
    """
    if not is_configured():
        return {
            "ok": False,
            "error": "not_configured",
            "live": False,
            "hint": (
                "Set DEFENDER_TENANT_ID / DEFENDER_CLIENT_ID / DEFENDER_CLIENT_SECRET "
                "and grant ThreatHunting.Read.All (Graph) or AdvancedHunting.Read.All (MTP)."
            ),
            "docs": {
                "graph": "https://learn.microsoft.com/en-us/graph/api/security-security-runhuntingquery",
                "legacy": "https://learn.microsoft.com/en-us/defender-xdr/api-advanced-hunting",
            },
        }
    limit = max(1, min(int(limit or 100), _MAX_RESULT_ROWS))
    q = _validate_query((query or "").strip() or DEFAULT_LIVE_QUERY)
    mode = backend or hunting_backend()
    async with httpx.AsyncClient(timeout=190.0) as client:
        if mode == "legacy":
            return await _run_legacy(client, q, limit)
        if mode == "graph":
            return await _run_graph(client, q, timespan, limit)
        try:
            return await _run_graph(client, q, timespan, limit)
        except Exception as graph_exc:
            try:
                out = await _run_legacy(client, q, limit)
                out["fallback_from"] = "graph"
                out["graph_error"] = str(graph_exc)[:300]
                return out
            except Exception as legacy_exc:
                return {
                    "ok": False,
                    "error": "hunting_failed",
                    "live": False,
                    "graph_error": str(graph_exc)[:400],
                    "legacy_error": str(legacy_exc)[:400],
                    "hint": (
                        "Grant ThreatHunting.Read.All (Graph) or AdvancedHunting.Read.All "
                        "(Microsoft Threat Protection) and admin-consent the app."
                    ),
                }


async def ping_hunting() -> dict[str, Any]:
    """Lightweight capability probe against the live tenant."""
    if not is_configured():
        return {
            "ok": False,
            "error": "not_configured",
            "live": False,
            "hint": "Configure DEFENDER_* credentials for live hunting.",
        }
    probe = "DeviceInfo | take 1 | project DeviceName, OSPlatform"
    result = await run_advanced_hunting(probe, limit=1)
    return {
        "ok": bool(result.get("ok")),
        "backend": result.get("backend"),
        "live": bool(result.get("ok")),
        "error": result.get("error") or result.get("graph_error") or result.get("legacy_error"),
        "result_count": result.get("result_count"),
    }
