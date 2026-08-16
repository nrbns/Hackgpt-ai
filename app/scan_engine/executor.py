"""Scan engine executor — queue worker runs scanners; AI does not."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.enterprise import create_vulnerability, ensure_asset_for_target
from app.scan_engine.models import (
    create_scan,
    evidence_root,
    get_scan,
    set_progress,
    update_scan,
)
from app.scanners.base import ScanContext
from app.scanners.registry import ENGINE_ENABLED, get_scanner
from app.services.tool_policy import normalize_scope_json
from app.db import now


async def execute_scan(scan_id: str) -> dict[str, Any]:
    scan = get_scan(scan_id)
    if not scan:
        raise ValueError(f"scan not found: {scan_id}")

    scanner_id = (scan.get("scanner") or "securaiq").lower()
    if scanner_id not in ENGINE_ENABLED:
        update_scan(scan_id, status="failed", error=f"Scanner '{scanner_id}' not engine-enabled yet", completed_at=now())
        raise ValueError(f"Scanner '{scanner_id}' not enabled")

    scanner = get_scanner(scanner_id)
    target = scan["target"]
    scope = normalize_scope_json(scan.get("scope") or [])
    authorized = bool(scan.get("authorized"))

    update_scan(scan_id, status="scope_check", started_at=now())
    set_progress(scan_id, "queued", "done")
    set_progress(scan_id, "scope", "active")

    if not authorized:
        update_scan(
            scan_id,
            status="blocked",
            error="Authorization checkbox required — only scan systems you own or are authorized to test",
            completed_at=now(),
        )
        set_progress(scan_id, "scope", "failed")
        return {"ok": False, "blocked": True, "reason": "not_authorized"}

    ok_t, t_detail = scanner.validate_target(target)
    if not ok_t:
        update_scan(scan_id, status="failed", error=t_detail, completed_at=now())
        return {"ok": False, "error": t_detail}

    ok_s, s_reason = scanner.validate_scope(t_detail, scope)
    if not ok_s:
        update_scan(scan_id, status="blocked", error=s_reason, completed_at=now())
        set_progress(scan_id, "scope", "failed")
        try:
            from app.realtime_bus import publish

            publish(type="scan", id=scan_id, status="blocked", reason=s_reason)
        except Exception:
            pass
        return {"ok": False, "blocked": True, "reason": s_reason}

    set_progress(scan_id, "scope", "done")
    avail, avail_detail = scanner.available()
    if not avail:
        update_scan(scan_id, status="failed", error=avail_detail, completed_at=now())
        return {"ok": False, "error": avail_detail}

    ev_dir = Path(scan.get("evidence_dir") or evidence_root(scan_id))
    ev_dir.mkdir(parents=True, exist_ok=True)
    ctx = ScanContext(
        scan_id=scan_id,
        target=t_detail,
        profile=scan.get("profile") or "discovery",
        scope=scope,
        authorized=authorized,
        evidence_dir=ev_dir,
        engagement_id=scan.get("engagement_id"),
        org_id=scan.get("org_id"),
        user_id=scan.get("user_id"),
    )

    update_scan(scan_id, status="running")
    set_progress(scan_id, "discovery", "active")
    set_progress(scan_id, "port_scan", "active")

    raw = await scanner.execute(ctx)

    set_progress(scan_id, "discovery", "done")
    set_progress(scan_id, "port_scan", "done")
    set_progress(scan_id, "service_detect", "done")
    update_scan(scan_id, status="collecting")
    set_progress(scan_id, "collecting", "done")

    update_scan(scan_id, status="parsing")
    set_progress(scan_id, "parsing", "active")
    parsed = scanner.parse(raw, ctx)
    set_progress(scan_id, "parsing", "done")

    update_scan(scan_id, status="normalizing")
    set_progress(scan_id, "normalizing", "active")
    normalized = scanner.normalize(parsed, ctx)
    set_progress(scan_id, "normalizing", "done")
    set_progress(scan_id, "risk", "active")

    user_id = scan["user_id"]
    notes = json.dumps(
        {
            "services": [s.__dict__ for s in normalized.services],
            "technologies": normalized.technologies,
            "scan_id": scan_id,
            "scanner": scanner_id,
        }
    )[:4000]
    asset = ensure_asset_for_target(
        user_id,
        normalized.asset_name,
        notes=notes,
        asset_type=normalized.asset_type or "host",
        engagement_id=scan.get("engagement_id"),
        org_id=scan.get("org_id"),
    )

    created = 0
    finding_rows: list[dict[str, Any]] = []
    for f in normalized.findings:
        item = {
            "title": f.title,
            "severity": f.severity,
            "asset_name": f.asset_name or normalized.asset_name,
            "asset_id": (asset or {}).get("id"),
            "cve": f.cve,
            "cvss": f.cvss,
            "source": f.source or f"scan:{scanner_id}",
            "engagement_id": scan.get("engagement_id"),
            "org_id": scan.get("org_id"),
            "raw": {
                **(f.raw or {}),
                "evidence": f.evidence,
                "scan_id": scan_id,
                "artifacts": raw.artifact_paths,
                "remediation": getattr(f, "remediation", None) or (f.raw or {}).get("remediation"),
            },
        }
        row = create_vulnerability(user_id, item, emit_realtime=True)
        finding_rows.append(row or item)
        created += 1

    summary = {
        **(normalized.summary or {}),
        "asset_id": (asset or {}).get("id"),
        "findings_created": created,
        "exit_code": raw.exit_code,
        "artifacts": list(raw.artifact_paths or []),
    }
    if raw.exit_code not in (0, None) and not normalized.services and not normalized.findings:
        err = (raw.stderr or raw.stdout or f"scanner exit {raw.exit_code}")[:2000]
        update_scan(
            scan_id,
            status="failed",
            error=err,
            summary_json=summary,
            completed_at=now(),
        )
        set_progress(scan_id, "risk", "failed")
        return {"ok": False, "error": err, "summary": summary}

    set_progress(scan_id, "risk", "done")
    set_progress(scan_id, "report", "active")
    from app.scan_engine.report import write_scan_report

    report_scan = {**scan, "summary": summary, "status": "completed", "id": scan_id}
    report_path = write_scan_report(ev_dir, report_scan, findings=finding_rows)
    summary["report"] = str(report_path)
    summary["report_url"] = f"/api/scans/{scan_id}/report"
    summary["report_pdf_url"] = f"/api/scans/{scan_id}/report.pdf"
    try:
        from app.commercial_ext import markdown_to_simple_pdf

        pdf_bytes = markdown_to_simple_pdf(
            report_path.read_text(encoding="utf-8"),
            title=f"SecuraIQ VA Report — {t_detail}",
        )
        pdf_path = ev_dir / "report.pdf"
        pdf_path.write_bytes(pdf_bytes)
        summary["report_pdf"] = str(pdf_path)
        if str(pdf_path) not in summary["artifacts"]:
            summary["artifacts"] = [*summary["artifacts"], str(pdf_path)]
    except Exception:
        pass
    if str(report_path) not in summary["artifacts"]:
        summary["artifacts"] = [*summary["artifacts"], str(report_path)]

    set_progress(scan_id, "report", "done")
    update_scan(
        scan_id,
        status="completed",
        summary_json=summary,
        completed_at=now(),
        error="",
    )
    try:
        from app.realtime_bus import publish

        publish(type="scan", id=scan_id, status="completed", summary=summary)
    except Exception:
        pass
    return {"ok": True, "scan_id": scan_id, "summary": summary}


def enqueue_scan_job(scan_id: str) -> dict[str, Any]:
    """Create background job linked to scan record."""
    import app.scan_engine.jobs  # noqa: F401 — ensure handler registered
    from app.jobs import enqueue_job

    job = enqueue_job("scan_execute", {"scan_id": scan_id})
    update_scan(scan_id, job_id=job.get("id"))
    return job
