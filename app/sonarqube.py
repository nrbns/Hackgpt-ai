"""SonarQube sync → vulnerability register (live API + realtime publish)."""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.connectors import sonarqube as sonar_conn
from app.db import audit
from app.enterprise import create_vulnerability, list_vulnerabilities
from app.scanner_adapters import parse_sonarqube


def status() -> dict[str, Any]:
    configured = sonar_conn.is_configured()
    return {
        "configured": configured,
        "brand": "SecuraIQ Code",
        "engine": "sonar_compatible",
        "base_url": (getattr(settings, "sonarqube_base_url", "") or "").rstrip("/") if configured else "",
        "project_key": (getattr(settings, "sonarqube_project_key", "") or "").strip(),
        "verify_ssl": bool(getattr(settings, "sonarqube_verify_ssl", True)),
        "sync_interval_sec": int(getattr(settings, "sonarqube_sync_interval_sec", 3600) or 3600),
        "issue_types": (getattr(settings, "sonarqube_issue_types", "") or "VULNERABILITY,SECURITY_HOTSPOT,BUG").strip(),
    }


def _existing_keys(user_id: str) -> set[str]:
    """Dedupe keys from prior Sonar imports: rule|component|key."""
    import json

    keys: set[str] = set()
    for v in list_vulnerabilities(user_id) or []:
        src = (v.get("source") or "").lower()
        if "sonarqube" not in src and "sonar" not in src and "securaiq_code" not in src:
            continue
        raw = v.get("raw") or v.get("raw_json") or {}
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = {}
        if not isinstance(raw, dict):
            continue
        issue = raw.get("raw") if isinstance(raw.get("raw"), dict) else raw
        if not isinstance(issue, dict):
            continue
        ik = str(issue.get("key") or "")
        if ik:
            keys.add(f"key:{ik}")
            continue
        rule = str(issue.get("rule") or v.get("cve") or "")
        comp = str(issue.get("component") or v.get("asset_name") or "")
        msg = str(issue.get("message") or v.get("title") or "")[:80]
        keys.add(f"{rule}|{comp}|{msg}")
    return keys


def _issue_key(issue: dict[str, Any]) -> str:
    ik = str(issue.get("key") or "")
    if ik:
        return f"key:{ik}"
    rule = str(issue.get("rule") or "")
    comp = str(issue.get("component") or issue.get("project") or "")
    msg = str(issue.get("message") or "")[:80]
    return f"{rule}|{comp}|{msg}"


async def sync(user_id: str = "local", *, engagement_id: str | None = None) -> dict[str, Any]:
    if not sonar_conn.is_configured():
        return {"ok": False, "error": "not_configured", "imported": 0, "skipped": 0}

    issues = await sonar_conn.fetch_issues()
    parsed = parse_sonarqube(
        {"issues": issues},
        engagement_id=engagement_id,
        filename="sonar-api",
    )
    existing = _existing_keys(user_id)
    imported = 0
    skipped = 0
    for item, issue in zip(parsed, issues):
        k = _issue_key(issue)
        if k in existing:
            skipped += 1
            continue
        item["source"] = "securaiq_code:api"
        item["raw"] = issue
        create_vulnerability(user_id, item)
        existing.add(k)
        imported += 1

    try:
        from app.realtime_bus import publish

        publish(type="vuln_batch", source="securaiq_code", count=imported, user_id=user_id)
    except Exception:
        pass

    audit(
        "securaiq_code_sync",
        user_id,
        {"imported": imported, "skipped": skipped, "fetched": len(issues)},
    )
    return {
        "ok": True,
        "imported": imported,
        "skipped": skipped,
        "fetched": len(issues),
        "configured": True,
        "brand": "SecuraIQ Code",
        "base_url": (getattr(settings, "sonarqube_base_url", "") or "").rstrip("/"),
        "project_key": (getattr(settings, "sonarqube_project_key", "") or "").strip(),
    }
