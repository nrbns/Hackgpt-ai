"""GitHub webhook → vulnerability register (live connector)."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any


def verify_signature(body: bytes, signature: str | None, secret: str) -> bool:
    if not secret:
        return False
    sig = (signature or "").strip()
    if not sig.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig[7:], expected)


def alerts_to_vuln_rows(payload: dict[str, Any], event: str) -> list[dict[str, Any]]:
    """Map GitHub security events to normalized vuln rows."""
    rows: list[dict[str, Any]] = []
    repo = (payload.get("repository") or {}).get("full_name") or "github"

    if event == "code_scanning_alert":
        alert = payload.get("alert") or {}
        rule = alert.get("rule") or {}
        rows.append(
            {
                "title": rule.get("description") or rule.get("name") or "Code scanning alert",
                "severity": _map_sev(alert.get("severity") or rule.get("severity")),
                "cve": "",
                "asset_name": repo,
                "source": "github:code_scanning",
                "raw_json": json.dumps({"event": event, "alert_id": alert.get("number")}),
            }
        )
    elif event == "dependabot_alert":
        alert = payload.get("alert") or {}
        adv = alert.get("security_advisory") or {}
        vuln = alert.get("security_vulnerability") or {}
        cve = ""
        for ident in adv.get("identifiers") or []:
            if (ident.get("type") or "").lower() == "cve":
                cve = ident.get("value") or ""
                break
        rows.append(
            {
                "title": adv.get("summary") or vuln.get("package", {}).get("name") or "Dependabot alert",
                "severity": _map_sev(alert.get("severity") or adv.get("severity")),
                "cve": cve,
                "asset_name": repo,
                "source": "github:dependabot",
                "raw_json": json.dumps({"event": event, "alert_number": alert.get("number")}),
            }
        )
    elif event == "secret_scanning_alert":
        alert = payload.get("alert") or {}
        rows.append(
            {
                "title": f"Secret scanning: {alert.get('secret_type') or 'exposed secret'}",
                "severity": "high",
                "cve": "",
                "asset_name": repo,
                "source": "github:secret_scanning",
                "raw_json": json.dumps({"event": event}),
            }
        )
    return rows


def _map_sev(raw: str | None) -> str:
    s = (raw or "medium").lower()
    if s in {"critical", "high", "medium", "low", "info"}:
        return s
    if s in {"error", "warning"}:
        return "high" if s == "error" else "medium"
    return "medium"
