"""Wazuh manager API connector — agents + alerts for authorized SOC labs.

Auth: POST /security/user/authenticate with HTTP Basic → JWT Bearer.
Alerts: prefer Wazuh Indexer (OpenSearch) when WAZUH_INDEXER_URL is set;
otherwise derive operational signals from disconnected agents and
vulnerability endpoints on the manager API.

Setup (.env / Settings):
  WAZUH_BASE_URL=https://wazuh.example:55000
  WAZUH_USER=wazuh-wui
  WAZUH_PASSWORD=...
  WAZUH_VERIFY_SSL=false   # labs often use self-signed certs
  # Optional Indexer for real alert pull:
  WAZUH_INDEXER_URL=https://indexer.example:9200
  WAZUH_INDEXER_USER=admin
  WAZUH_INDEXER_PASSWORD=...
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import settings

_token_cache: dict[str, Any] = {"token": "", "expires": 0.0}


def is_configured() -> bool:
    return bool(
        (settings.wazuh_base_url or "").strip()
        and (settings.wazuh_user or "").strip()
        and (settings.wazuh_password or "").strip()
    )


def indexer_configured() -> bool:
    return bool((settings.wazuh_indexer_url or "").strip())


def _verify() -> bool:
    return bool(getattr(settings, "wazuh_verify_ssl", False))


async def _authenticate(client: httpx.AsyncClient) -> str:
    now = time.time()
    if _token_cache["token"] and _token_cache["expires"] > now + 30:
        return str(_token_cache["token"])
    base = settings.wazuh_base_url.rstrip("/")
    resp = await client.post(
        f"{base}/security/user/authenticate",
        params={"raw": "true"},
        auth=(settings.wazuh_user, settings.wazuh_password),
    )
    if resp.status_code >= 400:
        raise ValueError(f"Wazuh auth failed {resp.status_code}: {resp.text[:300]}")
    token = (resp.text or "").strip().strip('"')
    if not token:
        # Some builds return JSON {"data":{"token":"..."}}
        try:
            token = ((resp.json() or {}).get("data") or {}).get("token") or ""
        except Exception:
            token = ""
    if not token:
        raise ValueError("Wazuh auth returned empty token")
    _token_cache["token"] = token
    _token_cache["expires"] = now + 800  # default JWT ~900s
    return token


async def _manager_get(path: str, params: dict[str, Any] | None = None) -> Any:
    base = settings.wazuh_base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=25.0, verify=_verify()) as client:
        token = await _authenticate(client)
        resp = await client.get(
            f"{base}{path}",
            params=params or {},
            headers={"Authorization": f"Bearer {token}"},
        )
    if resp.status_code >= 400:
        raise ValueError(f"Wazuh {path} error {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def _severity_from_level(level: Any) -> str:
    try:
        n = int(level)
    except (TypeError, ValueError):
        return "medium"
    if n >= 12:
        return "critical"
    if n >= 10:
        return "high"
    if n >= 7:
        return "medium"
    return "low"


async def fetch_agents(limit: int = 200) -> list[dict[str, Any]]:
    if not is_configured():
        return []
    data = await _manager_get(
        "/agents",
        {"limit": min(max(limit, 1), 500), "sort": "-lastKeepAlive"},
    )
    items = ((data or {}).get("data") or {}).get("affected_items") or []
    out: list[dict[str, Any]] = []
    for a in items:
        out.append(
            {
                "agent_id": str(a.get("id") or ""),
                "name": a.get("name") or "",
                "ip": a.get("ip") or "",
                "status": a.get("status") or "",
                "os": ((a.get("os") or {}).get("name") or a.get("os", {}).get("uname"))
                if isinstance(a.get("os"), dict)
                else str(a.get("os") or ""),
                "version": a.get("version") or "",
                "group": ",".join(a.get("group") or []) if isinstance(a.get("group"), list) else str(a.get("group") or ""),
                "last_keep_alive": a.get("lastKeepAlive") or "",
                "raw": a,
            }
        )
    return out


async def _fetch_alerts_from_indexer(limit: int = 100) -> list[dict[str, Any]]:
    url = settings.wazuh_indexer_url.rstrip("/")
    user = (settings.wazuh_indexer_user or settings.wazuh_user or "").strip()
    password = (settings.wazuh_indexer_password or settings.wazuh_password or "").strip()
    body = {
        "size": min(max(limit, 1), 200),
        "sort": [{"timestamp": {"order": "desc"}}],
        "query": {"bool": {"must": [{"match_all": {}}]}},
    }
    auth = (user, password) if user and password else None
    async with httpx.AsyncClient(timeout=30.0, verify=_verify()) as client:
        resp = await client.post(
            f"{url}/wazuh-alerts*/_search",
            json=body,
            auth=auth,
            headers={"Content-Type": "application/json"},
        )
    if resp.status_code >= 400:
        raise ValueError(f"Wazuh indexer error {resp.status_code}: {resp.text[:300]}")
    hits = (((resp.json() or {}).get("hits") or {}).get("hits")) or []
    out: list[dict[str, Any]] = []
    for h in hits:
        src = h.get("_source") or {}
        rule = src.get("rule") or {}
        agent = src.get("agent") or {}
        ext = h.get("_id") or src.get("id") or f"{src.get('timestamp')}-{rule.get('id')}"
        out.append(
            {
                "vendor": "wazuh",
                "external_id": str(ext),
                "kind": "siem_alert",
                "severity": _severity_from_level(rule.get("level")),
                "host": agent.get("name") or agent.get("id") or "",
                "title": rule.get("description") or src.get("full_log") or "Wazuh alert",
                "description": f"rule={rule.get('id')} mitre={rule.get('mitre') or rule.get('groups')}",
                "raw": src,
            }
        )
    return out


async def _fetch_signals_from_manager(limit: int = 100) -> list[dict[str, Any]]:
    """Fallback when Indexer is not configured — disconnected agents + vulns."""
    out: list[dict[str, Any]] = []
    agents = await fetch_agents(limit=min(limit, 200))
    for a in agents:
        status = (a.get("status") or "").lower()
        if status in {"disconnected", "never_connected", "pending"}:
            out.append(
                {
                    "vendor": "wazuh",
                    "external_id": f"agent-status-{a.get('agent_id')}-{status}",
                    "kind": "agent_health",
                    "severity": "high" if status == "disconnected" else "medium",
                    "host": a.get("name") or a.get("ip") or "",
                    "title": f"Wazuh agent {status}: {a.get('name') or a.get('agent_id')}",
                    "description": f"ip={a.get('ip')} version={a.get('version')} last={a.get('last_keep_alive')}",
                    "raw": a.get("raw") or a,
                }
            )
    try:
        data = await _manager_get("/vulnerability", {"limit": min(limit, 100)})
        items = ((data or {}).get("data") or {}).get("affected_items") or []
        for v in items[:limit]:
            agent = v.get("agent") or {}
            cve = v.get("cve") or v.get("name") or "vuln"
            out.append(
                {
                    "vendor": "wazuh",
                    "external_id": f"vuln-{agent.get('id')}-{cve}",
                    "kind": "vulnerability",
                    "severity": (v.get("severity") or "medium").lower(),
                    "host": agent.get("name") or "",
                    "title": f"{cve}: {v.get('title') or v.get('name') or 'Vulnerability'}",
                    "description": v.get("condition") or v.get("detection_time") or "",
                    "raw": v,
                }
            )
    except Exception:
        pass
    return out[:limit]


async def fetch_detections(limit: int = 100) -> list[dict[str, Any]]:
    """Normalized detections for XDR-style ingestion (vendor=wazuh)."""
    if not is_configured():
        return []
    if indexer_configured():
        try:
            return await _fetch_alerts_from_indexer(limit=limit)
        except Exception:
            # Fall through to manager signals so sync still produces value
            pass
    return await _fetch_signals_from_manager(limit=limit)


async def ping() -> dict[str, Any]:
    """Lightweight connectivity check for status UI."""
    if not is_configured():
        return {"ok": False, "error": "not_configured"}
    try:
        data = await _manager_get("/")
        return {
            "ok": True,
            "title": ((data or {}).get("data") or {}).get("title") or "Wazuh API",
            "api_version": ((data or {}).get("data") or {}).get("api_version") or "",
            "indexer": indexer_configured(),
        }
    except Exception as exc:
        _token_cache["token"] = ""
        _token_cache["expires"] = 0.0
        return {"ok": False, "error": str(exc)[:300]}
