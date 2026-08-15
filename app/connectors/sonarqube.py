"""SonarQube / SonarCloud Web API connector.

Auth: user token (Bearer) or Basic with token as username (SonarQube classic).

Setup (.env / Settings):
  SONARQUBE_BASE_URL=https://sonar.example.com
  SONARQUBE_TOKEN=squ_...
  SONARQUBE_PROJECT_KEY=   # optional filter
  SONARQUBE_VERIFY_SSL=true
  SONARQUBE_SYNC_INTERVAL_SEC=3600
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings

_UA = {"User-Agent": "SecuraIQ-SonarQube/1.0", "Accept": "application/json"}


def is_configured() -> bool:
    return bool(
        (getattr(settings, "sonarqube_base_url", "") or "").strip()
        and (getattr(settings, "sonarqube_token", "") or "").strip()
    )


def _verify() -> bool:
    return bool(getattr(settings, "sonarqube_verify_ssl", True))


def _base() -> str:
    return (getattr(settings, "sonarqube_base_url", "") or "").strip().rstrip("/")


def _headers() -> dict[str, str]:
    token = (getattr(settings, "sonarqube_token", "") or "").strip()
    # SonarCloud / modern SonarQube prefer Bearer; Basic(token,) also works
    return {**_UA, "Authorization": f"Bearer {token}"}


def _auth() -> httpx.BasicAuth | None:
    token = (getattr(settings, "sonarqube_token", "") or "").strip()
    if not token:
        return None
    # Classic SonarQube: token as username, empty password
    return httpx.BasicAuth(token, "")


async def ping() -> dict[str, Any]:
    if not is_configured():
        return {"ok": False, "error": "not_configured"}
    url = f"{_base()}/api/system/status"
    try:
        async with httpx.AsyncClient(timeout=20.0, verify=_verify()) as client:
            r = await client.get(url, headers=_headers())
            if r.status_code in {401, 403}:
                r = await client.get(url, auth=_auth(), headers=_UA)
            if r.status_code >= 400:
                return {"ok": False, "status_code": r.status_code, "error": (r.text or "")[:200]}
            data = r.json() if r.content else {}
            return {
                "ok": True,
                "status": (data.get("status") if isinstance(data, dict) else None) or "UP",
                "version": (data.get("version") if isinstance(data, dict) else None) or "",
            }
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}


async def fetch_issues(
    *,
    page_size: int = 100,
    max_pages: int = 10,
    types: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch open issues (security-focused by default)."""
    if not is_configured():
        return []
    project = (getattr(settings, "sonarqube_project_key", "") or "").strip()
    type_filter = (types or getattr(settings, "sonarqube_issue_types", "") or "VULNERABILITY,SECURITY_HOTSPOT,BUG").strip()
    out: list[dict[str, Any]] = []
    page = 1
    async with httpx.AsyncClient(timeout=60.0, verify=_verify()) as client:
        while page <= max_pages:
            params: dict[str, Any] = {
                "ps": min(500, max(1, page_size)),
                "p": page,
                "resolved": "false",
                "types": type_filter,
            }
            if project:
                params["componentKeys"] = project
            url = f"{_base()}/api/issues/search"
            r = await client.get(url, headers=_headers(), params=params)
            if r.status_code in {401, 403}:
                r = await client.get(url, auth=_auth(), headers=_UA, params=params)
            r.raise_for_status()
            data = r.json() if r.content else {}
            batch = data.get("issues") if isinstance(data, dict) else None
            if not isinstance(batch, list) or not batch:
                break
            out.extend([i for i in batch if isinstance(i, dict)])
            paging = data.get("paging") if isinstance(data, dict) else {}
            total = int((paging or {}).get("total") or 0)
            if len(out) >= total or len(batch) < params["ps"]:
                break
            page += 1
    return out
