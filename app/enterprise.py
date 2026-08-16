"""Structured enterprise workflows: risks, assets, vulnerabilities, remediations."""

from __future__ import annotations

import csv
import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from app.db import audit, get_conn, new_id, now, row_to_dict

SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


def _score(impact: int, likelihood: int) -> int:
    return max(1, min(25, int(impact) * int(likelihood)))


# --- Assets -----------------------------------------------------------------


def create_asset(
    user_id: str,
    name: str,
    *,
    asset_type: str = "server",
    criticality: str = "medium",
    owner: str = "",
    notes: str = "",
    engagement_id: str | None = None,
) -> dict[str, Any]:
    aid = new_id()
    ts = now()
    c = get_conn()
    c.execute(
        """
        INSERT INTO assets
        (id, user_id, engagement_id, name, asset_type, criticality, owner, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (aid, user_id, engagement_id, name.strip(), asset_type, criticality, owner, notes, ts, ts),
    )
    c.commit()
    audit("asset_create", user_id, {"id": aid, "name": name})
    try:
        from app.realtime_bus import publish

        publish(type="asset", id=aid, user_id=user_id)
    except Exception:
        pass
    return get_asset(user_id, aid)  # type: ignore[return-value]


def get_asset(user_id: str, asset_id: str) -> dict[str, Any] | None:
    row = get_conn().execute(
        "SELECT * FROM assets WHERE id = ? AND user_id = ?", (asset_id, user_id)
    ).fetchone()
    return row_to_dict(row)


def list_assets(user_id: str, engagement_id: str | None = None) -> list[dict[str, Any]]:
    c = get_conn()
    if engagement_id:
        rows = c.execute(
            "SELECT * FROM assets WHERE user_id = ? AND engagement_id = ? ORDER BY updated_at DESC",
            (user_id, engagement_id),
        ).fetchall()
    else:
        rows = c.execute(
            "SELECT * FROM assets WHERE user_id = ? ORDER BY updated_at DESC LIMIT 200",
            (user_id,),
        ).fetchall()
    return [row_to_dict(r) for r in rows]  # type: ignore[misc]


def update_asset(user_id: str, asset_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    row = get_asset(user_id, asset_id)
    if not row:
        return None
    allowed = {"name", "asset_type", "criticality", "owner", "notes", "engagement_id"}
    data = {k: v for k, v in patch.items() if k in allowed and v is not None}
    if not data:
        return row
    data["updated_at"] = now()
    sets = ", ".join(f"{k} = ?" for k in data)
    get_conn().execute(
        f"UPDATE assets SET {sets} WHERE id = ? AND user_id = ?",
        (*data.values(), asset_id, user_id),
    )
    get_conn().commit()
    audit("asset_update", user_id, {"id": asset_id, **data})
    return get_asset(user_id, asset_id)


def delete_asset(user_id: str, asset_id: str) -> bool:
    cur = get_conn().execute(
        "DELETE FROM assets WHERE id = ? AND user_id = ?", (asset_id, user_id)
    )
    get_conn().commit()
    if cur.rowcount:
        audit("asset_delete", user_id, {"id": asset_id})
        return True
    return False


# --- Risks ------------------------------------------------------------------


def create_risk(
    user_id: str,
    *,
    threat: str,
    vulnerability: str = "",
    asset_name: str = "",
    asset_id: str | None = None,
    impact: int = 3,
    likelihood: int = 3,
    owner: str = "",
    mitigation: str = "",
    status: str = "open",
    engagement_id: str | None = None,
) -> dict[str, Any]:
    rid = new_id()
    ts = now()
    score = _score(impact, likelihood)
    c = get_conn()
    c.execute(
        """
        INSERT INTO risks
        (id, user_id, engagement_id, asset_id, asset_name, threat, vulnerability,
         impact, likelihood, risk_score, owner, mitigation, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            rid, user_id, engagement_id, asset_id, asset_name, threat.strip(), vulnerability,
            impact, likelihood, score, owner, mitigation, status, ts, ts,
        ),
    )
    c.commit()
    audit("risk_create", user_id, {"id": rid, "score": score})
    try:
        from app.realtime_bus import publish

        publish(type="risk", id=rid, user_id=user_id, score=score)
    except Exception:
        pass
    return get_risk(user_id, rid)  # type: ignore[return-value]


def get_risk(user_id: str, risk_id: str) -> dict[str, Any] | None:
    row = get_conn().execute(
        "SELECT * FROM risks WHERE id = ? AND user_id = ?", (risk_id, user_id)
    ).fetchone()
    return row_to_dict(row)


def list_risks(
    user_id: str,
    *,
    engagement_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    c = get_conn()
    q = "SELECT * FROM risks WHERE user_id = ?"
    args: list[Any] = [user_id]
    if engagement_id:
        q += " AND engagement_id = ?"
        args.append(engagement_id)
    if status:
        q += " AND status = ?"
        args.append(status)
    q += " ORDER BY risk_score DESC, updated_at DESC LIMIT 500"
    return [row_to_dict(r) for r in c.execute(q, args).fetchall()]  # type: ignore[misc]


def update_risk(user_id: str, risk_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    cur = get_risk(user_id, risk_id)
    if not cur:
        return None
    fields = {
        "threat", "vulnerability", "asset_name", "asset_id", "impact", "likelihood",
        "owner", "mitigation", "status", "engagement_id",
    }
    data = {k: patch[k] for k in fields if k in patch}
    if "impact" in data or "likelihood" in data:
        impact = int(data.get("impact", cur["impact"]))
        likelihood = int(data.get("likelihood", cur["likelihood"]))
        data["impact"] = impact
        data["likelihood"] = likelihood
        data["risk_score"] = _score(impact, likelihood)
    if not data:
        return cur
    data["updated_at"] = now()
    sets = ", ".join(f"{k} = ?" for k in data)
    get_conn().execute(
        f"UPDATE risks SET {sets} WHERE id = ? AND user_id = ?",
        (*data.values(), risk_id, user_id),
    )
    get_conn().commit()
    audit("risk_update", user_id, {"id": risk_id, **{k: data[k] for k in data if k != "updated_at"}})
    updated = get_risk(user_id, risk_id)
    try:
        from app.realtime_bus import publish

        publish(type="risk", id=risk_id, score=(updated or {}).get("risk_score"), user_id=user_id)
    except Exception:
        pass
    return updated


def delete_risk(user_id: str, risk_id: str) -> bool:
    c = get_conn()
    cur = c.execute("DELETE FROM risks WHERE id = ? AND user_id = ?", (risk_id, user_id))
    c.commit()
    return cur.rowcount > 0


# --- Vulnerabilities --------------------------------------------------------


def create_vulnerability(
    user_id: str,
    item: dict[str, Any],
    *,
    emit_realtime: bool = True,
) -> dict[str, Any]:
    vid = new_id()
    ts = now()
    c = get_conn()
    c.execute(
        """
        INSERT INTO vulnerabilities
        (id, user_id, engagement_id, asset_id, asset_name, cve, title, severity, cvss,
         status, owner, sla_due, source, raw_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            vid,
            user_id,
            item.get("engagement_id"),
            item.get("asset_id"),
            item.get("asset_name") or item.get("asset") or "",
            (item.get("cve") or "").upper(),
            item.get("title") or "Untitled finding",
            (item.get("severity") or "medium").lower(),
            item.get("cvss"),
            item.get("status") or "open",
            item.get("owner") or "",
            item.get("sla_due") or "",
            item.get("source") or "import",
            json.dumps(item.get("raw") or item),
            ts,
            ts,
        ),
    )
    c.commit()
    result = get_vulnerability(user_id, vid)

    if emit_realtime:
        try:
            from app.realtime_bus import publish

            publish(
                type="vuln",
                id=vid,
                severity=(item.get("severity") or "medium").lower(),
                user_id=user_id,
            )
        except Exception:
            pass

    severity = (item.get("severity") or "medium").lower()
    if severity in ("critical", "high"):
        from app.notifications import notify

        title = item.get("title") or "Untitled finding"
        asset = item.get("asset_name") or item.get("asset") or "unknown"
        cve = (item.get("cve") or "n/a").upper()

        notify(
            user_id,
            "critical_vuln",
            f"New {severity} vulnerability: {title}",
            f"Asset: {asset} · CVE: {cve} · Source: {item.get('source') or 'import'}",
            link=f"/api/vulnerabilities/{vid}",
            email=(severity == "critical"),
        )

        if severity == "critical":
            import asyncio

            from app.connectors import slack, teams

            alert_text = f"🔴 *Critical vulnerability*: {title}\nAsset: {asset} · CVE: {cve}"
            if slack.is_configured():
                asyncio.create_task(slack.send_message(alert_text))
            if teams.is_configured():
                asyncio.create_task(teams.send_message("Critical vulnerability", alert_text))

    return result  # type: ignore[return-value]


def get_vulnerability(user_id: str, vuln_id: str) -> dict[str, Any] | None:
    row = get_conn().execute(
        "SELECT * FROM vulnerabilities WHERE id = ? AND user_id = ?", (vuln_id, user_id)
    ).fetchone()
    return row_to_dict(row)


def list_vulnerabilities(
    user_id: str,
    *,
    engagement_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    c = get_conn()
    q = "SELECT * FROM vulnerabilities WHERE user_id = ?"
    args: list[Any] = [user_id]
    if engagement_id:
        q += " AND engagement_id = ?"
        args.append(engagement_id)
    if status:
        q += " AND status = ?"
        args.append(status)
    q += " ORDER BY created_at DESC LIMIT 1000"
    rows = [row_to_dict(r) for r in c.execute(q, args).fetchall()]
    rows.sort(key=lambda r: SEVERITY_RANK.get((r or {}).get("severity", "medium"), 2), reverse=True)
    return rows  # type: ignore[return-value]


def update_vulnerability(user_id: str, vuln_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    cur = get_vulnerability(user_id, vuln_id)
    if not cur:
        return None
    fields = {"status", "owner", "sla_due", "severity", "title", "asset_name", "cve"}
    data = {k: patch[k] for k in fields if k in patch}
    if not data:
        return cur
    data["updated_at"] = now()
    sets = ", ".join(f"{k} = ?" for k in data)
    get_conn().execute(
        f"UPDATE vulnerabilities SET {sets} WHERE id = ? AND user_id = ?",
        (*data.values(), vuln_id, user_id),
    )
    get_conn().commit()
    audit("vuln_update", user_id, {"id": vuln_id, "status": data.get("status")})
    updated = get_vulnerability(user_id, vuln_id)
    try:
        from app.realtime_bus import publish

        publish(
            type="vuln",
            id=vuln_id,
            severity=(updated or {}).get("severity") or "medium",
            status=(updated or {}).get("status") or "",
            user_id=user_id,
        )
    except Exception:
        pass
    return updated


def triage_vulnerability(
    user_id: str,
    vuln_id: str,
    *,
    owner: str = "SecOps",
    create_ticket_hint: bool = False,
) -> dict[str, Any]:
    """Golden-path writeback: finding → risk + remediation + in_progress status."""
    v = get_vulnerability(user_id, vuln_id)
    if not v:
        raise ValueError("Vulnerability not found")

    sev = (v.get("severity") or "medium").lower()
    impact = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}.get(sev, 3)
    likelihood = 4 if sev in {"critical", "high"} else 3
    sla = {"critical": "24h", "high": "72h", "medium": "14d", "low": "30d"}.get(sev, "14d")
    cve = (v.get("cve") or "").strip()
    title = (v.get("title") or "Finding").strip()
    threat = f"{cve + ' — ' if cve else ''}{title}"[:500]
    asset = (v.get("asset_name") or "").strip()
    own = (owner or v.get("owner") or "SecOps").strip() or "SecOps"

    risk = create_risk(
        user_id,
        threat=threat,
        vulnerability=cve or title[:200],
        asset_name=asset,
        asset_id=v.get("asset_id"),
        impact=impact,
        likelihood=likelihood,
        owner=own,
        mitigation=f"Triage from vulnerability {vuln_id}. Verify fix and re-scan.",
        status="open",
        engagement_id=v.get("engagement_id"),
    )
    rem = create_remediation(
        user_id,
        control_id="VM",
        title=f"Remediate: {threat}"[:300],
        owner=own,
        due_date=sla,
        recommendation=(
            f"Prioritize {sev} finding on {asset or 'unknown asset'}. "
            f"Validate patch/config, then close finding after verification scan."
        ),
        engagement_id=v.get("engagement_id"),
    )
    updated = update_vulnerability(
        user_id,
        vuln_id,
        {"status": "in_progress", "owner": own, "sla_due": sla},
    )
    audit(
        "vuln_triage",
        user_id,
        {"vuln_id": vuln_id, "risk_id": risk.get("id"), "remediation_id": rem.get("id")},
    )
    return {
        "ok": True,
        "vulnerability": updated,
        "risk": risk,
        "remediation": rem,
        "create_ticket_hint": create_ticket_hint,
        "workflow_step": "triaged",
    }


def import_vulnerabilities(
    user_id: str,
    *,
    content: str | bytes,
    filename: str,
    engagement_id: str | None = None,
) -> dict[str, Any]:
    from app.scanner_adapters import try_parse_scanner_json

    name = (filename or "import").lower()
    text = content.decode("utf-8", errors="replace") if isinstance(content, (bytes, bytearray)) else content
    items: list[dict[str, Any]] = []
    adapter = None

    if name.endswith(".json") or text.strip().startswith(("[", "{")):
        adapter, scanned = try_parse_scanner_json(text, filename=filename, engagement_id=engagement_id)
        if adapter and scanned:
            items.extend(scanned)
        else:
            data = json.loads(text)
            if isinstance(data, dict):
                data = data.get("vulnerabilities") or data.get("findings") or data.get("issues") or [data]
            for row in data:
                if not isinstance(row, dict):
                    continue
                items.append(_normalize_vuln_row(row, engagement_id, source=f"json:{filename}"))
    elif name.endswith(".csv") or "," in text.split("\n", 1)[0]:
        from app.hardeningkitty import is_hardeningkitty_report, parse_report_csv

        if is_hardeningkitty_report(text, filename):
            adapter = "hardeningkitty"
            items.extend(parse_report_csv(text, engagement_id=engagement_id, filename=filename))
        else:
            reader = csv.DictReader(io.StringIO(text))
            for row in reader:
                items.append(_normalize_vuln_row(dict(row), engagement_id, source=f"csv:{filename}"))
    elif name.endswith(".xml") or text.strip().startswith("<"):
        from app.scanner_adapters import is_burp_xml, parse_burp_xml

        if is_burp_xml(text):
            adapter = "burp"
            items.extend(parse_burp_xml(text, engagement_id=engagement_id, filename=filename))
        else:
            items.extend(_parse_xml_vulns(text, engagement_id, filename))
    else:
        raise ValueError(
            "Unsupported format — use CSV, JSON, XML, HardeningKitty report CSV, or scanner JSON "
            "(Trivy/Semgrep/Gitleaks/Grype/Checkov/Bandit/SonarQube/ZAP)"
        )

    created = []
    for it in items[:500]:
        # Suppress per-row bus spam on bulk import — one vuln_batch below
        created.append(create_vulnerability(user_id, it, emit_realtime=False))
    if created:
        try:
            from app.realtime_bus import publish

            publish(
                type="vuln_batch",
                source=adapter or "import",
                count=len(created),
                file=filename,
                user_id=user_id,
            )
        except Exception:
            pass
    audit(
        "vuln_import",
        user_id,
        {"file": filename, "count": len(created), "adapter": adapter or "generic"},
    )
    return {"imported": len(created), "adapter": adapter or "generic", "vulnerabilities": created[:50]}


def _normalize_vuln_row(row: dict[str, Any], engagement_id: str | None, source: str) -> dict[str, Any]:
    from app.scanner_adapters import _sev_norm

    lower = {str(k).lower().strip(): v for k, v in row.items()}
    title = (
        lower.get("title")
        or lower.get("name")
        or lower.get("plugin name")
        or lower.get("vulnerability")
        or lower.get("finding")
        or "Imported finding"
    )
    cve = lower.get("cve") or lower.get("cve_id") or lower.get("cve-id") or ""
    severity = str(lower.get("severity") or lower.get("risk") or lower.get("severity_label") or "medium")
    asset = lower.get("asset") or lower.get("host") or lower.get("ip") or lower.get("asset_name") or ""
    cvss_raw = lower.get("cvss") or lower.get("cvss_score") or lower.get("cvssv3") or None
    try:
        cvss = float(cvss_raw) if cvss_raw not in (None, "") else None
    except (TypeError, ValueError):
        cvss = None
    return {
        "title": str(title)[:300],
        "cve": str(cve)[:40],
        # Route every generic/CSV/XML import (Nessus, Qualys exports, etc.) through
        # the same critical/high/medium/low/info normalization the dedicated scanner
        # adapters use — a naive lowercase-first-word split silently produced values
        # like "information" or "blocker" that never matched any severity filter/badge.
        "severity": _sev_norm(severity, "medium"),
        "asset_name": str(asset)[:200],
        "cvss": cvss,
        "engagement_id": engagement_id,
        "source": source,
        "raw": row,
    }


def _parse_xml_vulns(text: str, engagement_id: str | None, filename: str) -> list[dict[str, Any]]:
    root = ET.fromstring(text)
    items: list[dict[str, Any]] = []
    # Generic: look for ReportItem / issue / vulnerability nodes
    candidates = (
        root.findall(".//ReportItem")
        + root.findall(".//vulnerability")
        + root.findall(".//issue")
        + root.findall(".//finding")
    )
    if not candidates:
        candidates = list(root)
    for node in candidates[:500]:
        def _t(*keys: str) -> str:
            for k in keys:
                v = node.findtext(k) or node.get(k)
                if v:
                    return v.strip()
            return ""

        title = _t("plugin_name", "name", "title", "PluginName") or node.tag
        items.append(
            _normalize_vuln_row(
                {
                    "title": title,
                    "cve": _t("cve", "CVE"),
                    "severity": _t("severity", "risk", "Risk", "severity"),
                    "asset": _t("host", "ip", "target", "Host"),
                    "cvss": _t("cvss", "cvss_base_score"),
                },
                engagement_id,
                source=f"xml:{filename}",
            )
        )
    return items


# --- Gap remediations -------------------------------------------------------


def _ensure_assessment_id(
    c: Any,
    user_id: str,
    assessment_id: str | None,
    engagement_id: str | None = None,
) -> str:
    """Resolve a real gap_assessments.id (FK required by gap_remediations)."""
    if assessment_id:
        row = c.execute("SELECT id FROM gap_assessments WHERE id = ?", (assessment_id,)).fetchone()
        if row:
            return str(row[0])
    row = c.execute(
        "SELECT id FROM gap_assessments WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    if row:
        return str(row[0])
    # Per-user Mission Control bucket for one-click tasks without a prior gap run
    aid = f"mission-control:{user_id}"
    ts = now()
    c.execute(
        """
        INSERT OR IGNORE INTO gap_assessments
        (id, user_id, engagement_id, framework_id, title, evidence, result_json,
         compliance_percent, created_at)
        VALUES (?, ?, ?, 'iso27001', 'Mission Control work queue', '', '{}', 0, ?)
        """,
        (aid, user_id, engagement_id, ts),
    )
    return aid


def create_remediation(
    user_id: str,
    *,
    control_id: str = "MC",
    title: str,
    owner: str = "",
    due_date: str = "",
    recommendation: str = "",
    engagement_id: str | None = None,
    assessment_id: str | None = None,
) -> dict[str, Any]:
    rid = new_id()
    ts = now()
    c = get_conn()
    aid = _ensure_assessment_id(c, user_id, assessment_id, engagement_id)
    c.execute(
        """
        INSERT INTO gap_remediations
        (id, assessment_id, user_id, engagement_id, control_id, title, status,
         owner, due_date, notes, recommendation, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, '', ?, ?, ?)
        """,
        (
            rid,
            aid,
            user_id,
            engagement_id,
            (control_id or "MC")[:40],
            (title or "Task")[:300],
            (owner or "")[:120],
            (due_date or "")[:40],
            (recommendation or title or "")[:2000],
            ts,
            ts,
        ),
    )
    c.commit()
    audit("remediation_create", user_id, {"id": rid, "title": title})
    try:
        from app.realtime_bus import publish

        publish(type="remediation", id=rid, user_id=user_id)
    except Exception:
        pass
    rows = list_remediations(user_id)
    return next((r for r in rows if r.get("id") == rid), {"id": rid, "title": title, "status": "open"})


def create_remediations_from_assessment(
    user_id: str,
    assessment_id: str,
    gaps: list[dict[str, Any]],
    engagement_id: str | None = None,
) -> list[dict[str, Any]]:
    """Persist trackable remediation tasks for missing/partial controls."""
    c = get_conn()
    # clear prior open tasks for this assessment (re-run)
    c.execute("DELETE FROM gap_remediations WHERE assessment_id = ?", (assessment_id,))
    out = []
    ts = now()
    for g in gaps:
        if g.get("status") not in {"missing", "partial"}:
            continue
        rid = new_id()
        c.execute(
            """
            INSERT INTO gap_remediations
            (id, assessment_id, user_id, engagement_id, control_id, title, status,
             owner, due_date, notes, recommendation, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'open', '', '', '', ?, ?, ?)
            """,
            (
                rid,
                assessment_id,
                user_id,
                engagement_id,
                g.get("control_id") or "",
                g.get("title") or "",
                g.get("recommendation") or "",
                ts,
                ts,
            ),
        )
        out.append(
            {
                "id": rid,
                "assessment_id": assessment_id,
                "control_id": g.get("control_id"),
                "title": g.get("title"),
                "status": "open",
                "recommendation": g.get("recommendation"),
            }
        )
    c.commit()
    audit("gap_remediations_seed", user_id, {"assessment_id": assessment_id, "count": len(out)})
    if out:
        try:
            from app.realtime_bus import publish

            publish(type="remediation", id=assessment_id, count=len(out), user_id=user_id)
        except Exception:
            pass
    return out


def list_remediations(
    user_id: str,
    *,
    assessment_id: str | None = None,
    engagement_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    c = get_conn()
    q = "SELECT * FROM gap_remediations WHERE user_id = ?"
    args: list[Any] = [user_id]
    if assessment_id:
        q += " AND assessment_id = ?"
        args.append(assessment_id)
    if engagement_id:
        q += " AND engagement_id = ?"
        args.append(engagement_id)
    if status:
        q += " AND status = ?"
        args.append(status)
    q += " ORDER BY updated_at DESC LIMIT 500"
    return [row_to_dict(r) for r in c.execute(q, args).fetchall()]  # type: ignore[misc]


def update_remediation(user_id: str, rem_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    row = get_conn().execute(
        "SELECT * FROM gap_remediations WHERE id = ? AND user_id = ?", (rem_id, user_id)
    ).fetchone()
    if not row:
        return None
    fields = {"status", "owner", "due_date", "notes"}
    data = {k: patch[k] for k in fields if k in patch}
    if not data:
        return row_to_dict(row)
    data["updated_at"] = now()
    sets = ", ".join(f"{k} = ?" for k in data)
    get_conn().execute(
        f"UPDATE gap_remediations SET {sets} WHERE id = ? AND user_id = ?",
        (*data.values(), rem_id, user_id),
    )
    get_conn().commit()
    audit("gap_remediation_update", user_id, {"id": rem_id, **data})
    updated = get_conn().execute(
        "SELECT * FROM gap_remediations WHERE id = ? AND user_id = ?", (rem_id, user_id)
    ).fetchone()
    result = row_to_dict(updated)
    try:
        from app.realtime_bus import publish

        publish(
            type="remediation",
            id=rem_id,
            status=(result or {}).get("status") or "",
            user_id=user_id,
        )
    except Exception:
        pass
    return result


def evidence_from_files(user_id: str, file_ids: list[str]) -> str:
    """Load uploaded file text for gap analysis evidence."""
    chunks: list[str] = []
    c = get_conn()
    for fid in file_ids[:20]:
        row = c.execute(
            "SELECT * FROM files WHERE id = ? AND user_id = ?", (fid, user_id)
        ).fetchone()
        if not row:
            continue
        path = Path(row["stored_path"])
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        chunks.append(f"--- FILE: {row['filename']} ---\n{text[:40_000]}")
    return "\n\n".join(chunks)


def enterprise_dashboard(user_id: str) -> dict[str, Any]:
    from app.gap_analysis import dashboard_scores, get_assessment
    from app.ops import list_incidents, list_intel_watch, purge_demo_seed
    from app.workspace import list_audit

    purge_demo_seed(user_id)
    gap = dashboard_scores(user_id)
    risks = list_risks(user_id)
    vulns = list_vulnerabilities(user_id)
    remediations = list_remediations(user_id)
    assets = list_assets(user_id)
    playbooks = list_playbooks(user_id)
    campaigns = list_campaigns(user_id)
    incidents = list_incidents(user_id)
    intel_watch = list_intel_watch(user_id)

    open_risks = [r for r in risks if (r.get("status") or "") == "open"]
    open_vulns = [v for v in vulns if (v.get("status") or "") == "open"]
    open_rems = [r for r in remediations if (r.get("status") or "open") != "done"]
    crit_vulns = [v for v in open_vulns if (v.get("severity") or "") in {"critical", "high"}]
    active_campaigns = [c for c in campaigns if (c.get("status") or "") in {"planned", "running"}]
    open_incidents = [i for i in incidents if (i.get("status") or "") == "open"]
    pending_approvals: list[dict[str, Any]] = [
        {
            "id": r.get("id"),
            "title": r.get("title") or r.get("control_id") or "Remediation",
            "owner": r.get("owner") or "Unassigned",
            "status": r.get("status") or "open",
            "control_id": r.get("control_id") or "",
            "kind": "remediation",
        }
        for r in open_rems[:8]
    ]
    for i in open_incidents[:4]:
        pending_approvals.append(
            {
                "id": i.get("id"),
                "title": i.get("title") or "Incident",
                "owner": i.get("owner") or "Unassigned",
                "status": i.get("status") or "open",
                "control_id": "",
                "kind": "incident",
            }
        )

    avg_risk = round(sum(r.get("risk_score") or 0 for r in open_risks) / max(len(open_risks), 1), 1)

    frameworks = gap.get("frameworks") or []
    is_empty = not any(
        [
            assets,
            vulns,
            risks,
            remediations,
            incidents,
            campaigns,
            playbooks,
            intel_watch,
            frameworks,
            gap.get("assessment_count"),
        ]
    )

    # Security index — empty workspaces stay at 0 (not a fake mid-score from “no findings”)
    compliance = float(gap.get("compliance_score") or 0)
    if is_empty:
        security_index = 0
    else:
        security_index = max(
            0,
            min(
                100,
                round(
                    compliance * 0.55
                    + max(0, 100 - len(open_risks) * 4) * 0.2
                    + max(0, 100 - len(crit_vulns) * 8) * 0.15
                    + max(0, 100 - len(open_rems) * 2) * 0.1
                ),
            ),
        )

    kpi_now = {
        "index": security_index,
        "comp": compliance,
        "crit": len(crit_vulns),
        "risks": len(open_risks),
        "rems": len(open_rems),
        "assets": len(assets),
        "incidents": len(open_incidents),
    }
    kpi_trends = (
        {"has_baseline": False, "security_index_delta": 0, "compliance_delta": 0, "vulns_delta": 0, "risks_delta": 0, "rems_delta": 0, "assets_delta": 0, "incidents_delta": 0}
        if is_empty
        else _compute_kpi_trends(user_id, kpi_now)
    )
    if is_empty:
        try:
            from app.config import settings as _settings

            snap = Path(_settings.data_dir) / "kpi_snaps" / f"{user_id}.json"
            if snap.exists():
                snap.unlink(missing_ok=True)
        except Exception:
            pass

    primary_fw = frameworks[0] if frameworks else None
    org_name = "Local workspace"
    try:
        from app.commercial_ext import list_orgs

        orgs = list_orgs(user_id)
        if orgs:
            org_name = orgs[0].get("name") or org_name
    except Exception:
        pass

    last_scan = None
    for v in vulns[:1]:
        last_scan = v.get("updated_at") or v.get("created_at")
    if not last_scan and frameworks:
        last_scan = primary_fw.get("created_at") if primary_fw else None

    work_queue = _work_queue(gap, open_risks, crit_vulns or open_vulns, open_rems, assets, playbooks)
    timeline = _organization_timeline(user_id, list_audit, open_vulns, open_risks, remediations)
    asset_breakdown = _asset_breakdown(assets)
    mitre = _mitre_coverage(open_vulns, playbooks, open_risks)
    control_stats = _framework_control_stats(user_id, get_assessment, frameworks)

    correlation: dict[str, Any] = {"hotspots": [], "counts": {}}
    try:
        from app.knowledge_graph import build_knowledge_graph

        g = build_knowledge_graph(user_id)
        correlation = {
            "hotspots": g.get("hotspots") or [],
            "counts": g.get("counts") or {},
            "doctrine": g.get("doctrine") or "",
        }
    except Exception:
        pass

    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for v in vulns:
        if (v.get("status") or "") in {"closed", "resolved", "fixed"}:
            continue
        s = (v.get("severity") or "medium").lower()
        if s in severity_counts:
            severity_counts[s] += 1

    return {
        **gap,
        "is_empty": is_empty,
        "security_index": security_index,
        "correlation": correlation,
        "severity_counts": severity_counts,
        "risks_open": len(open_risks),
        "risks_total": len(risks),
        "avg_open_risk_score": avg_risk,
        "vulnerabilities_open": len(open_vulns),
        "vulnerabilities_critical_high": len(crit_vulns),
        "vulnerabilities_total": len(vulns),
        "remediations_open": len(open_rems),
        "remediations_total": len(remediations),
        "assets_total": len(assets),
        "playbooks_total": len(playbooks),
        "campaigns_active": len(active_campaigns),
        "campaigns_total": len(campaigns),
        "findings": {
            "top_risks": open_risks[:5],
            "top_vulns": crit_vulns[:5] or open_vulns[:5],
            "top_remediations": open_rems[:5],
            "top_playbooks": playbooks[:5],
            "top_campaigns": active_campaigns[:5] or campaigns[:5],
        },
        "recommendations": [w["title"] for w in work_queue],
        "work_queue": work_queue,
        "needs_attention": pending_approvals,
        "mission_control": {
            "organization": org_name,
            "environment": "Production" if org_name != "Local workspace" else "Lab / local",
            "framework": (primary_fw or {}).get("framework_id") or "—",
            "framework_score": (primary_fw or {}).get("compliance_percent"),
            "security_score": security_index,
            "last_scan": last_scan,
            "today": {
                "critical_findings": len(crit_vulns),
                "open_risks": len(open_risks),
                "open_actions": len(open_rems),
                "open_incidents": len(open_incidents),
                "controls_failed": sum(
                    1 for f in frameworks if float(f.get("compliance_percent") or 0) < 50
                ),
            },
        },
        "pending_approvals": pending_approvals,
        "intel": {
            "watch_count": len(intel_watch),
            "watch": [
                {
                    "id": w.get("id"),
                    "kind": w.get("kind"),
                    "value": w.get("value"),
                    "notes": w.get("notes") or "",
                }
                for w in intel_watch[:6]
            ],
        },
        "incidents_open": len(open_incidents),
        "incidents_total": len(incidents),
        "workflow": {
            "imported": len(vulns),
            "open": len(open_vulns),
            "triaged": len(
                [v for v in vulns if (v.get("status") or "") in {"in_progress", "triaged", "accepted"}]
            ),
            "actions": len(open_rems),
            "closed": len([v for v in vulns if (v.get("status") or "") in {"closed", "resolved", "fixed"}]),
            "risks": len(open_risks),
        },
        "asset_breakdown": asset_breakdown,
        "timeline": timeline,
        "mitre_coverage": mitre,
        "framework_control_stats": control_stats,
        "kpi_trends": kpi_trends,
        "morning_brief": _morning_brief(
            org_name=org_name,
            security_index=security_index,
            compliance=compliance,
            crit=len(crit_vulns),
            risks=len(open_risks),
            rems=len(open_rems),
            incidents=len(open_incidents),
            work_queue=work_queue,
            framework=(primary_fw or {}).get("framework_id") or "",
            is_empty=is_empty,
        ),
    }


def _morning_brief(
    *,
    org_name: str,
    security_index: int | float,
    compliance: float,
    crit: int,
    risks: int,
    rems: int,
    incidents: int,
    work_queue: list[dict[str, Any]],
    framework: str,
    is_empty: bool = False,
) -> dict[str, Any]:
    """Deterministic morning AI summary (no model call) for Mission Control home."""
    hour = __import__("datetime").datetime.now().hour
    hello = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
    if is_empty:
        summary = (
            f"{hello}. {org_name} starts at zero — no assets, findings, or assessments yet. "
            "Import a scanner export or run gap analysis when you are ready."
        )
        attention = "Your workspace is empty by design."
        next_step = "Import a scanner export, add assets, or run a gap analysis with your evidence."
    elif crit == 0 and risks == 0 and incidents == 0 and not work_queue:
        summary = (
            f"{hello}. {org_name} is quiet — no critical findings or open incidents. "
            "Import a scanner export or run gap analysis when you are ready."
        )
        attention = "Maintain baseline monitoring and keep evidence current."
        next_step = "Connect integrations or import an authorized scanner export."
    else:
        top = (work_queue[0]["title"] if work_queue else "Triage critical findings")
        summary = (
            f"{hello}. Security score is {int(security_index)} with {compliance:.0f}% "
            f"{(framework or 'compliance')}. "
            f"Attention: {crit} critical/high, {risks} open risks, {incidents} incidents, "
            f"{rems} open remediations."
        )
        attention = top
        next_step = (
            work_queue[0].get("ai")
            if work_queue
            else "Triage top vulnerabilities, assign owners, and link evidence."
        )
    return {
        "greeting": hello,
        "summary": summary,
        "attention": attention,
        "next_step": next_step,
        "generated": "rules",  # model optional later
    }


def _compute_kpi_trends(user_id: str, current: dict[str, Any]) -> dict[str, Any]:
    """Persist last KPI snapshot and return deltas for Mission Control trends."""
    from app.config import settings

    snap_dir = Path(settings.data_dir) / "kpi_snaps"
    path = snap_dir / f"{user_id}.json"
    prev: dict[str, Any] = {}
    has_baseline = path.exists()
    if has_baseline:
        try:
            prev = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            prev = {}
            has_baseline = False
    try:
        snap_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({**current, "at": now()}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

    def delta(key: str) -> int:
        if not has_baseline:
            return 0
        return int(round(float(current.get(key) or 0) - float(prev.get(key) or 0)))

    return {
        "has_baseline": has_baseline,
        "security_index_delta": delta("index"),
        "compliance_delta": delta("comp"),
        "vulns_delta": delta("crit"),
        "risks_delta": delta("risks"),
        "rems_delta": delta("rems"),
        "assets_delta": delta("assets"),
        "incidents_delta": delta("incidents"),
    }


def _work_queue(
    gap: dict[str, Any],
    risks: list[dict[str, Any]],
    vulns: list[dict[str, Any]],
    rems: list[dict[str, Any]],
    assets: list[dict[str, Any]],
    playbooks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    def add(
        *,
        priority: str,
        title: str,
        owner: str = "Unassigned",
        due: str = "This week",
        status: str = "open",
        action: str = "task",
        mode: str = "ciso",
        prompt: str = "",
        workspace: str | None = None,
        framework: str = "",
        risk: str | int | float = "",
        ai: str = "",
        entity_id: str = "",
    ) -> None:
        items.append(
            {
                "id": f"wq-{len(items)+1}",
                "priority": priority,
                "title": title,
                "owner": owner,
                "due": due,
                "status": status,
                "action": action,
                "mode": mode,
                "prompt": prompt or title,
                "workspace": workspace,
                "framework": framework,
                "risk": risk,
                "ai": ai or "Ask AI for root cause, impact, and remediation steps.",
                "entity_id": entity_id or "",
            }
        )

    # Empty workspace: no synthetic tasks — only queue real register items
    if not gap.get("assessment_count") and not vulns and not risks and not rems and not assets:
        return []

    if not gap.get("assessment_count") and (vulns or risks or rems):
        add(
            priority="high",
            title="Run gap analysis and attach evidence",
            owner="Compliance",
            due="Today",
            action="gap",
            mode="ciso",
            prompt="Guide me through an ISO 27001 gap analysis with evidence mapping",
            workspace="frameworks",
            framework="ISO 27001",
            risk="Compliance drift",
            ai="Map evidence to controls; run Gap analysis next.",
        )
    for v in vulns[:2]:
        add(
            priority="high" if (v.get("severity") or "") == "critical" else "medium",
            title=f"Patch / triage {v.get('cve') or v.get('title')}",
            owner=v.get("owner") or "SecOps",
            due=v.get("sla_due") or "72h",
            action="open",
            mode="blueteam",
            prompt=f"Draft remediation and verification for {v.get('cve') or ''} {v.get('title')}",
            workspace="vulns",
            risk=v.get("severity") or "",
            ai=f"Triage {v.get('cve') or 'finding'} → remediate → verify.",
            entity_id=str(v.get("id") or ""),
        )
    if risks:
        top = risks[0]
        add(
            priority="high" if (top.get("risk_score") or 0) >= 15 else "medium",
            title=f"Mitigate risk: {top.get('threat')}",
            owner=top.get("owner") or "Risk owner",
            due="This week",
            action="open",
            mode="ciso",
            prompt=f"Draft mitigation plan for risk: {top.get('threat')}",
            workspace="risks",
            risk=top.get("risk_score") or "",
            ai="Reduce likelihood/impact; set residual score.",
            entity_id=str(top.get("id") or ""),
        )
    for r in rems[:2]:
        add(
            priority="medium",
            title=f"Close control {r.get('control_id')}: {r.get('title')}",
            owner=r.get("owner") or "Control owner",
            due=r.get("due_date") or "30 days",
            action="open",
            mode="ciso",
            prompt=f"Implementation checklist for {r.get('control_id')} — {r.get('title')}",
            workspace="remediations",
            framework=str(r.get("framework_id") or r.get("control_id") or ""),
            ai="Attach evidence and close when verified.",
            entity_id=str(r.get("id") or ""),
        )
    # de-dupe by title, keep priority order high>medium>low
    order = {"high": 0, "medium": 1, "low": 2}
    seen: set[str] = set()
    uniq: list[dict[str, Any]] = []
    for it in sorted(items, key=lambda x: order.get(x["priority"], 9)):
        if it["title"] in seen:
            continue
        seen.add(it["title"])
        uniq.append(it)
    return uniq[:8]


def _asset_breakdown(assets: list[dict[str, Any]]) -> dict[str, int]:
    buckets = {"server": 0, "endpoint": 0, "cloud": 0, "container": 0, "other": 0}
    for a in assets:
        t = (a.get("asset_type") or "other").lower()
        if t in {"server", "servers", "vm"}:
            buckets["server"] += 1
        elif t in {"endpoint", "laptop", "workstation", "desktop"}:
            buckets["endpoint"] += 1
        elif t in {"cloud", "saas", "aws", "azure", "gcp"}:
            buckets["cloud"] += 1
        elif t in {"container", "k8s", "kubernetes", "pod"}:
            buckets["container"] += 1
        else:
            buckets["other"] += 1
    return buckets


def _organization_timeline(
    user_id: str,
    list_audit_fn,
    vulns: list[dict[str, Any]],
    risks: list[dict[str, Any]],
    rems: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    try:
        for ev in list_audit_fn(40):
            if ev.get("user_id") not in (None, user_id, "local"):
                # include local + this user
                if user_id == "local":
                    pass
                elif ev.get("user_id") != user_id:
                    continue
            action = ev.get("action") or "event"
            events.append(
                {
                    "ts": ev.get("created_at"),
                    "label": action.replace("_", " "),
                    "detail": (
                        json.dumps(ev.get("detail"))[:120]
                        if isinstance(ev.get("detail"), (dict, list))
                        else str(ev.get("detail") or "")[:120]
                    ),
                    "kind": "audit",
                }
            )
    except Exception:
        pass
    for v in vulns[:3]:
        events.append(
            {
                "ts": v.get("updated_at") or v.get("created_at"),
                "label": f"Vuln {v.get('severity')}",
                "detail": f"{v.get('cve') or ''} {v.get('title')}".strip(),
                "kind": "vuln",
            }
        )
    for r in risks[:2]:
        events.append(
            {
                "ts": r.get("updated_at") or r.get("created_at"),
                "label": "Risk open",
                "detail": r.get("threat") or "",
                "kind": "risk",
            }
        )
    for rem in rems[:2]:
        if (rem.get("status") or "") == "done":
            events.append(
                {
                    "ts": rem.get("updated_at") or rem.get("created_at"),
                    "label": "Control closed",
                    "detail": f"{rem.get('control_id')} {rem.get('title')}",
                    "kind": "remediation",
                }
            )
    events.sort(key=lambda e: float(e.get("ts") or 0), reverse=True)
    return events[:12]


def _mitre_coverage(
    vulns: list[dict[str, Any]],
    playbooks: list[dict[str, Any]],
    risks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Heuristic coverage bars for executive view — not a full ATT&CK mapping."""
    text = " ".join(
        f"{v.get('title','')} {v.get('cve','')}" for v in vulns
    ).lower() + " " + " ".join(p.get("title", "") for p in playbooks).lower()
    text += " " + " ".join(r.get("threat", "") for r in risks).lower()

    tactics = [
        ("Discovery", ["scan", "recon", "enum", "discover"]),
        ("Execution", ["rce", "remote code", "script", "execute"]),
        ("Persistence", ["persist", "backdoor", "startup", "cron"]),
        ("Privilege Escalation", ["privesc", "privilege", "sudo", "admin"]),
        ("Defense Evasion", ["evasion", "bypass", "disable"]),
        ("Credential Access", ["password", "credential", "mfa", "token"]),
        ("Lateral Movement", ["lateral", "rdp", "smb", "pivot"]),
        ("Exfiltration", ["exfil", "leak", "upload", "data loss"]),
    ]
    out = []
    for name, kws in tactics:
        hits = sum(1 for k in kws if k in text)
        # Honest estimate: no fake floor when nothing matches
        base = hits * 22
        if playbooks and name.lower() in " ".join(
            (p.get("category") or "") + " " + (p.get("title") or "") for p in playbooks
        ).lower():
            base += 15
        out.append({"tactic": name, "coverage": min(95, base)})
    return out


def _framework_control_stats(user_id: str, get_assessment, frameworks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-assessment control counts for Mission Control + Frameworks UI."""
    stats: list[dict[str, Any]] = []
    for f in frameworks:
        aid = f.get("id")
        counts = {"implemented": 0, "partial": 0, "missing": 0, "not_applicable": 0}
        total = 0
        if aid:
            try:
                detail = get_assessment(user_id, aid)
                if detail and detail.get("counts"):
                    counts.update({k: int(detail["counts"].get(k) or 0) for k in counts})
                    total = int(detail.get("control_count") or 0) or sum(counts.values())
            except Exception:
                pass
        stats.append(
            {
                "framework_id": f.get("framework_id"),
                "title": f.get("title"),
                "compliance_percent": f.get("compliance_percent"),
                "controls_total": total,
                "counts": counts,
                "assessment_id": aid,
            }
        )
    return stats


def _live_recommendations(
    gap: dict[str, Any],
    risks: list[dict[str, Any]],
    vulns: list[dict[str, Any]],
    rems: list[dict[str, Any]],
    assets: list[dict[str, Any]] | None = None,
    playbooks: list[dict[str, Any]] | None = None,
    campaigns: list[dict[str, Any]] | None = None,
) -> list[str]:
    # Kept for backward compatibility — prefer work_queue
    return [
        w["title"]
        for w in _work_queue(gap, risks, vulns, rems, assets or [], playbooks or [])
    ][:6]


def export_risk_markdown(user_id: str, engagement_id: str | None = None) -> str:
    risks = list_risks(user_id, engagement_id=engagement_id)
    lines = ["# Risk Assessment Report", "", f"Open/tracked risks: **{len(risks)}**", ""]
    lines += [
        "| Asset | Threat | Vuln | I | L | Score | Owner | Status |",
        "|---|---|---|---:|---:|---:|---|---|",
    ]
    for r in risks:
        lines.append(
            f"| {r.get('asset_name') or '-'} | {r.get('threat')} | {r.get('vulnerability') or '-'} | "
            f"{r.get('impact')} | {r.get('likelihood')} | {r.get('risk_score')} | "
            f"{r.get('owner') or '-'} | {r.get('status')} |"
        )
    lines += ["", "---", "_SecuraIQ structured risk register export._"]
    return "\n".join(lines)


def export_vuln_markdown(user_id: str, engagement_id: str | None = None) -> str:
    vulns = list_vulnerabilities(user_id, engagement_id=engagement_id)
    lines = ["# Vulnerability Summary", "", f"Findings: **{len(vulns)}**", ""]
    lines += [
        "| Severity | CVE | Title | Asset | Status | Owner |",
        "|---|---|---|---|---|---|",
    ]
    for v in vulns:
        lines.append(
            f"| {v.get('severity')} | {v.get('cve') or '-'} | {v.get('title')} | "
            f"{v.get('asset_name') or '-'} | {v.get('status')} | {v.get('owner') or '-'} |"
        )
    lines += ["", "---", "_SecuraIQ vulnerability register export._"]
    return "\n".join(lines)


# --- Playbooks --------------------------------------------------------------

_DEFAULT_PLAYBOOKS = [
    {
        "title": "Ransomware — workstation containment",
        "category": "ir",
        "severity": "critical",
        "steps": (
            "1. Isolate host from network\n"
            "2. Preserve volatile evidence / EDR timeline\n"
            "3. Reset credentials for interactive users\n"
            "4. Check backup integrity before restore\n"
            "5. Exec + legal notification checklist"
        ),
    },
    {
        "title": "Business email compromise (BEC)",
        "category": "ir",
        "severity": "high",
        "steps": (
            "1. Disable suspect mailbox rules / forwarding\n"
            "2. Force sign-out + MFA reset\n"
            "3. Trace recent mail flow and finance wires\n"
            "4. Notify partners if invoices were altered\n"
            "5. Awareness follow-up within 7 days"
        ),
    },
    {
        "title": "Suspected insider data staging",
        "category": "ir",
        "severity": "high",
        "steps": (
            "1. Preserve logs without tipping off subject\n"
            "2. Legal / HR coordination\n"
            "3. Restrict access to sensitive shares\n"
            "4. Collect DLP / USB / cloud sync evidence\n"
            "5. Post-incident access review"
        ),
    },
]



def reset_workspace(user_id: str, *, clear_rag: bool = False) -> dict[str, Any]:
    """Wipe operational data for a user so Mission Control starts at zero. Keeps auth accounts."""
    c = get_conn()
    counts: dict[str, int] = {}

    # Child rows first where needed
    chat_ids = [
        r["id"]
        for r in c.execute("SELECT id FROM chats WHERE user_id = ?", (user_id,)).fetchall()
    ]
    if chat_ids:
        placeholders = ",".join("?" * len(chat_ids))
        cur = c.execute(f"DELETE FROM messages WHERE chat_id IN ({placeholders})", chat_ids)
        counts["messages"] = int(cur.rowcount or 0)

    tables = [
        "chats",
        "memories",
        "files",
        "gap_remediations",
        "gap_assessments",
        "assets",
        "risks",
        "vulnerabilities",
        "playbooks",
        "campaigns",
        "incidents",
        "intel_watch",
        "entity_links",
        "webhooks",
        "evidence_links",
        "engagements",
        "notifications",
        "action_approvals",
        "usage_events",
    ]
    for table in tables:
        try:
            cur = c.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
            counts[table] = int(cur.rowcount or 0)
        except Exception:
            counts[table] = counts.get(table, 0)

    # Global operational queues (no user_id) — always clear so Automation starts empty
    for table in ("xdr_events", "jobs", "wazuh_agents", "openaudit_devices", "hardeningkitty_runs"):
        try:
            cur = c.execute(f"DELETE FROM {table}")
            counts[table] = int(cur.rowcount or 0)
        except Exception:
            counts[table] = counts.get(table, 0)

    # Organizations owned / joined by this user
    try:
        from app.commercial_ext import ensure_org_schema

        ensure_org_schema()
        org_ids = [
            r["org_id"]
            for r in c.execute("SELECT org_id FROM org_members WHERE user_id = ?", (user_id,)).fetchall()
        ]
        cur = c.execute("DELETE FROM org_members WHERE user_id = ?", (user_id,))
        counts["org_members"] = int(cur.rowcount or 0)
        orgs_deleted = 0
        for oid in org_ids:
            left = c.execute("SELECT 1 FROM org_members WHERE org_id = ? LIMIT 1", (oid,)).fetchone()
            if left:
                continue
            c.execute("DELETE FROM organizations WHERE id = ?", (oid,))
            orgs_deleted += 1
        counts["organizations"] = orgs_deleted
    except Exception:
        counts["organizations"] = counts.get("organizations", 0)

    c.commit()
    audit("workspace_reset", user_id, {"counts": counts, "clear_rag": clear_rag})

    # Clear KPI trend baseline so empty UI does not show stale deltas
    try:
        from app.config import settings as _settings

        snap = Path(_settings.data_dir) / "kpi_snaps" / f"{user_id}.json"
        if snap.exists():
            snap.unlink(missing_ok=True)
            counts["kpi_snap"] = 1
    except Exception:
        pass

    rag_cleared = False
    if clear_rag:
        try:
            from app.config import settings as _settings
            from app.rag import rag_engine

            if hasattr(rag_engine, "reset"):
                rag_engine.reset()
                rag_cleared = True
            else:
                persist = Path(_settings.chroma_persist_dir)
                if persist.exists():
                    import shutil

                    shutil.rmtree(persist, ignore_errors=True)
                    rag_cleared = True
        except Exception:
            rag_cleared = False

    return {"ok": True, "deleted": counts, "rag_cleared": rag_cleared}


def apply_workspace_zero_start() -> dict[str, Any] | None:
    """Nil / zero boot for open local mode — Mission Control starts empty."""
    from app.config import settings as _settings

    if _settings.auth_enabled or not getattr(_settings, "workspace_zero_start", False):
        return None

    user_ids: set[str] = {"local"}
    c = get_conn()
    for table in (
        "assets",
        "risks",
        "vulnerabilities",
        "engagements",
        "gap_assessments",
        "incidents",
        "playbooks",
        "campaigns",
        "notifications",
        "chats",
    ):
        try:
            for row in c.execute(f"SELECT DISTINCT user_id FROM {table}"):
                uid = row[0] if not isinstance(row, dict) else row.get("user_id")
                if uid:
                    user_ids.add(str(uid))
        except Exception:
            continue

    result: dict[str, Any] = {"users": [], "deleted": {}}
    for uid in sorted(user_ids):
        wiped = reset_workspace(uid, clear_rag=False)
        result["users"].append(uid)
        result["deleted"][uid] = wiped.get("deleted") or {}

    # Clear KPI snap files
    try:
        snap_dir = Path(_settings.data_dir) / "kpi_snaps"
        if snap_dir.is_dir():
            for snap in snap_dir.glob("*.json"):
                snap.unlink(missing_ok=True)
    except Exception:
        pass

    print(
        "Workspace: zero-start applied (nil UI). "
        "Set WORKSPACE_ZERO_START=false to keep data across restarts."
    )
    return result


def ensure_default_playbooks(user_id: str) -> None:
    """No-op — playbooks start empty; users add their own."""
    return


def create_playbook(
    user_id: str,
    *,
    title: str,
    category: str = "ir",
    severity: str = "high",
    steps: str = "",
    status: str = "ready",
    owner: str = "",
    engagement_id: str | None = None,
) -> dict[str, Any]:
    pid = new_id()
    ts = now()
    c = get_conn()
    c.execute(
        """
        INSERT INTO playbooks
        (id, user_id, engagement_id, title, category, severity, steps, status, owner, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (pid, user_id, engagement_id, title.strip(), category, severity, steps, status, owner, ts, ts),
    )
    c.commit()
    audit("playbook_create", user_id, {"id": pid, "title": title})
    try:
        from app.realtime_bus import publish

        publish(type="playbook", id=pid, user_id=user_id)
    except Exception:
        pass
    return get_playbook(user_id, pid)  # type: ignore[return-value]


def get_playbook(user_id: str, playbook_id: str) -> dict[str, Any] | None:
    row = get_conn().execute(
        "SELECT * FROM playbooks WHERE id = ? AND user_id = ?", (playbook_id, user_id)
    ).fetchone()
    return row_to_dict(row)


def list_playbooks(user_id: str, engagement_id: str | None = None) -> list[dict[str, Any]]:
    c = get_conn()
    if engagement_id:
        rows = c.execute(
            "SELECT * FROM playbooks WHERE user_id = ? AND engagement_id = ? ORDER BY updated_at DESC",
            (user_id, engagement_id),
        ).fetchall()
    else:
        rows = c.execute(
            "SELECT * FROM playbooks WHERE user_id = ? ORDER BY updated_at DESC LIMIT 200",
            (user_id,),
        ).fetchall()
    return [row_to_dict(r) for r in rows]  # type: ignore[misc]


def update_playbook(user_id: str, playbook_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    row = get_playbook(user_id, playbook_id)
    if not row:
        return None
    allowed = {"title", "category", "severity", "steps", "status", "owner", "engagement_id"}
    data = {k: v for k, v in patch.items() if k in allowed and v is not None}
    if not data:
        return row
    data["updated_at"] = now()
    sets = ", ".join(f"{k} = ?" for k in data)
    get_conn().execute(
        f"UPDATE playbooks SET {sets} WHERE id = ? AND user_id = ?",
        (*data.values(), playbook_id, user_id),
    )
    get_conn().commit()
    audit("playbook_update", user_id, {"id": playbook_id, **data})
    return get_playbook(user_id, playbook_id)


def delete_playbook(user_id: str, playbook_id: str) -> bool:
    cur = get_conn().execute(
        "DELETE FROM playbooks WHERE id = ? AND user_id = ?", (playbook_id, user_id)
    )
    get_conn().commit()
    if cur.rowcount:
        audit("playbook_delete", user_id, {"id": playbook_id})
        return True
    return False


# --- Awareness campaigns ----------------------------------------------------


def create_campaign(
    user_id: str,
    *,
    name: str,
    campaign_type: str = "phishing_sim",
    audience: str = "",
    status: str = "planned",
    sent_count: int = 0,
    click_count: int = 0,
    report_count: int = 0,
    notes: str = "",
    engagement_id: str | None = None,
) -> dict[str, Any]:
    cid = new_id()
    ts = now()
    c = get_conn()
    c.execute(
        """
        INSERT INTO campaigns
        (id, user_id, engagement_id, name, campaign_type, audience, status,
         sent_count, click_count, report_count, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cid,
            user_id,
            engagement_id,
            name.strip(),
            campaign_type,
            audience,
            status,
            int(sent_count),
            int(click_count),
            int(report_count),
            notes,
            ts,
            ts,
        ),
    )
    c.commit()
    audit("campaign_create", user_id, {"id": cid, "name": name})
    try:
        from app.realtime_bus import publish

        publish(type="campaign", id=cid, user_id=user_id)
    except Exception:
        pass
    return get_campaign(user_id, cid)  # type: ignore[return-value]


def get_campaign(user_id: str, campaign_id: str) -> dict[str, Any] | None:
    row = get_conn().execute(
        "SELECT * FROM campaigns WHERE id = ? AND user_id = ?", (campaign_id, user_id)
    ).fetchone()
    return row_to_dict(row)


def list_campaigns(user_id: str, engagement_id: str | None = None) -> list[dict[str, Any]]:
    c = get_conn()
    if engagement_id:
        rows = c.execute(
            "SELECT * FROM campaigns WHERE user_id = ? AND engagement_id = ? ORDER BY updated_at DESC",
            (user_id, engagement_id),
        ).fetchall()
    else:
        rows = c.execute(
            "SELECT * FROM campaigns WHERE user_id = ? ORDER BY updated_at DESC LIMIT 200",
            (user_id,),
        ).fetchall()
    return [row_to_dict(r) for r in rows]  # type: ignore[misc]


def update_campaign(user_id: str, campaign_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    row = get_campaign(user_id, campaign_id)
    if not row:
        return None
    allowed = {
        "name",
        "campaign_type",
        "audience",
        "status",
        "sent_count",
        "click_count",
        "report_count",
        "notes",
        "engagement_id",
    }
    data = {k: v for k, v in patch.items() if k in allowed and v is not None}
    if not data:
        return row
    data["updated_at"] = now()
    sets = ", ".join(f"{k} = ?" for k in data)
    get_conn().execute(
        f"UPDATE campaigns SET {sets} WHERE id = ? AND user_id = ?",
        (*data.values(), campaign_id, user_id),
    )
    get_conn().commit()
    audit("campaign_update", user_id, {"id": campaign_id, **data})
    return get_campaign(user_id, campaign_id)


def delete_campaign(user_id: str, campaign_id: str) -> bool:
    cur = get_conn().execute(
        "DELETE FROM campaigns WHERE id = ? AND user_id = ?", (campaign_id, user_id)
    )
    get_conn().commit()
    if cur.rowcount:
        audit("campaign_delete", user_id, {"id": campaign_id})
        return True
    return False
