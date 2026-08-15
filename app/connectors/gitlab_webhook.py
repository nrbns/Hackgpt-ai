"""GitLab webhook → vulnerability register (mirrors GitHub connector)."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any


def verify_token(header_token: str | None, secret: str) -> bool:
    """GitLab uses a shared secret in X-Gitlab-Token (not HMAC by default)."""
    if not secret:
        return False
    return hmac.compare_digest((header_token or "").strip(), secret.strip())


def verify_signature(body: bytes, signature: str | None, secret: str) -> bool:
    """Optional GitLab webhook signing secret (X-Gitlab-Token HMAC variants)."""
    if not secret:
        return False
    # Prefer simple token match (GitLab UI default)
    if signature and not signature.startswith("sha256="):
        return verify_token(signature, secret)
    sig = (signature or "").strip()
    if not sig.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig[7:], expected)


def alerts_to_vuln_rows(payload: dict[str, Any], event: str) -> list[dict[str, Any]]:
    """Map GitLab security / SAST / Dependabot-style events to vuln rows."""
    rows: list[dict[str, Any]] = []
    project = (payload.get("project") or {}).get("path_with_namespace") or (
        (payload.get("project") or {}).get("name") or "gitlab"
    )
    event_l = (event or payload.get("object_kind") or "").lower()

    if event_l in {"vulnerability", "vulnerability_hooks"} or payload.get("object_kind") == "vulnerability":
        obj = payload.get("object_attributes") or payload
        rows.append(
            {
                "title": obj.get("title") or obj.get("name") or "GitLab vulnerability",
                "severity": _map_sev(obj.get("severity")),
                "cve": _extract_cve(obj),
                "asset_name": project,
                "source": "gitlab:vulnerability",
                "raw_json": json.dumps({"event": event_l, "id": obj.get("id") or obj.get("iid")}),
            }
        )
    elif "pipeline" in event_l or payload.get("object_kind") == "pipeline":
        # Security report artifacts are often attached to pipelines — acknowledge only
        return rows
    elif event_l in {"push", "tag_push"}:
        return rows

    # Generic: vulnerabilities array (some GitLab webhook formats)
    for v in payload.get("vulnerabilities") or []:
        if not isinstance(v, dict):
            continue
        rows.append(
            {
                "title": v.get("name") or v.get("message") or "GitLab finding",
                "severity": _map_sev(v.get("severity")),
                "cve": _extract_cve(v),
                "asset_name": project,
                "source": "gitlab:report",
                "raw_json": json.dumps({"event": event_l}),
            }
        )
    return rows


def _extract_cve(obj: dict[str, Any]) -> str:
    for key in ("cve", "cve_id", "identifier"):
        val = obj.get(key)
        if isinstance(val, str) and val.upper().startswith("CVE-"):
            return val
    for ident in obj.get("identifiers") or []:
        if isinstance(ident, dict):
            name = ident.get("name") or ident.get("value") or ""
            if str(name).upper().startswith("CVE-"):
                return str(name)
        elif isinstance(ident, str) and ident.upper().startswith("CVE-"):
            return ident
    return ""


def _map_sev(raw: str | None) -> str:
    s = (raw or "medium").lower()
    if s in {"critical", "high", "medium", "low", "info", "unknown"}:
        return "medium" if s == "unknown" else s
    if s in {"error", "warning"}:
        return "high" if s == "error" else "medium"
    return "medium"
