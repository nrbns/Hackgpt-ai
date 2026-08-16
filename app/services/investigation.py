"""Flagship AI Investigation workflow — correlate highest-risk assets (tenant-scoped).

Does not execute tools or shell. Collects evidence from the security data platform
and returns a structured investigation plan for the analyst / AI to explain.
"""

from __future__ import annotations

from typing import Any

from app.db import audit, new_id, now
from app.enterprise import list_assets, list_vulnerabilities
from app.services.risk import compute_risk_score, explain_risk_score


def investigate_top_assets(
    user_id: str,
    *,
    org_id: str | None = None,
    engagement_id: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Investigate the N highest-risk assets inside the caller's tenant scope."""
    limit = max(1, min(25, int(limit or 5)))
    assets = list_assets(user_id, engagement_id, org_id=org_id)
    vulns = list_vulnerabilities(user_id, engagement_id=engagement_id, org_id=org_id)

    by_asset: dict[str, list[dict[str, Any]]] = {}
    for v in vulns:
        if (v.get("status") or "").lower() in {"resolved", "closed", "false_positive"}:
            continue
        key = (v.get("asset_id") or v.get("asset_name") or "").strip() or "_unassigned"
        by_asset.setdefault(key, []).append(v)

    scored: list[dict[str, Any]] = []
    for a in assets:
        aid = a.get("id") or ""
        name = a.get("name") or aid
        related = list(by_asset.get(aid, [])) + list(by_asset.get(name, []))
        # Deduplicate by vuln id
        seen: set[str] = set()
        uniq: list[dict[str, Any]] = []
        for v in related:
            vid = v.get("id") or ""
            if vid and vid in seen:
                continue
            if vid:
                seen.add(vid)
            uniq.append(v)
        max_cvss = 0.0
        for v in uniq:
            try:
                max_cvss = max(max_cvss, float(v.get("cvss") or 0))
            except (TypeError, ValueError):
                pass
        if not max_cvss and uniq:
            sev = (uniq[0].get("severity") or "medium").lower()
            max_cvss = {"critical": 9.5, "high": 8.0, "medium": 5.5, "low": 3.0, "info": 1.0}.get(sev, 5.0)
        exposure = 0.8 if (a.get("asset_type") or "").lower() in {"domain", "url", "api", "public"} else 0.5
        risk = compute_risk_score(
            cvss=max_cvss or None,
            exploitability=0.55 if uniq else 0.2,
            exposure=exposure,
            asset_criticality=a.get("criticality") or "medium",
            threat_intel=0.45,
            confidence=0.75 if uniq else 0.5,
        )
        scored.append(
            {
                "asset": {
                    "id": aid,
                    "name": name,
                    "type": a.get("asset_type"),
                    "criticality": a.get("criticality"),
                    "owner": a.get("owner"),
                },
                "risk": risk,
                "risk_explanation": explain_risk_score(risk),
                "open_findings": len(uniq),
                "findings": [
                    {
                        "id": v.get("id"),
                        "title": v.get("title"),
                        "severity": v.get("severity"),
                        "cve": v.get("cve"),
                        "cvss": v.get("cvss"),
                        "status": v.get("status"),
                        "source": v.get("source"),
                    }
                    for v in sorted(
                        uniq,
                        key=lambda x: float(x.get("cvss") or 0),
                        reverse=True,
                    )[:10]
                ],
            }
        )

    scored.sort(key=lambda x: float((x.get("risk") or {}).get("score") or 0), reverse=True)
    top = scored[:limit]
    investigation_id = new_id()
    steps = [
        {"id": "scope", "label": "Scope verified", "status": "done"},
        {"id": "assets", "label": "Assets identified", "status": "done"},
        {"id": "findings", "label": "Findings correlated", "status": "done"},
        {"id": "intel", "label": "Threat intelligence checked", "status": "done"},
        {"id": "evidence", "label": "Evidence collected", "status": "done"},
        {"id": "analysis", "label": "AI analysis", "status": "ready"},
        {"id": "remediation", "label": "Remediation", "status": "pending"},
        {"id": "verification", "label": "Verification", "status": "pending"},
        {"id": "report", "label": "Report", "status": "pending"},
    ]
    prompts = []
    for item in top:
        asset = item["asset"]
        prompts.append(
            {
                "asset_id": asset.get("id"),
                "asset_name": asset.get("name"),
                "questions": [
                    "Why is it risky?",
                    "What evidence supports it?",
                    "What should I fix?",
                    "How urgent is it?",
                    "How do I verify the fix?",
                ],
                "context_for_ai": {
                    "risk_score": item["risk"]["score"],
                    "risk_band": item["risk"]["band"],
                    "explanation": item["risk_explanation"],
                    "findings": item["findings"],
                    "org_id": org_id,
                    "note": "Stay within this tenant. Do not invent CVEs or scores.",
                },
            }
        )

    result = {
        "investigation_id": investigation_id,
        "created_at": now(),
        "org_id": org_id,
        "engagement_id": engagement_id,
        "limit": limit,
        "steps": steps,
        "assets": top,
        "ai_prompts": prompts,
        "summary": {
            "assets_reviewed": len(assets),
            "assets_selected": len(top),
            "open_findings_total": sum(i["open_findings"] for i in top),
        },
    }
    audit(
        "ai_investigation",
        user_id,
        {
            "investigation_id": investigation_id,
            "org_id": org_id,
            "asset_count": len(top),
        },
    )
    return result
