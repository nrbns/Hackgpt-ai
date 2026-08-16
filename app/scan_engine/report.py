"""Scan report artifacts — markdown summary under evidence/scans/{id}/."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.db import now


def build_scan_report_md(
    scan: dict[str, Any],
    *,
    findings: list[dict[str, Any]] | None = None,
) -> str:
    """Build a human-readable scan report (Markdown)."""
    summary = scan.get("summary") or {}
    if isinstance(summary, str):
        try:
            import json

            summary = json.loads(summary) or {}
        except Exception:
            summary = {}
    findings = findings or []
    target = scan.get("target") or "—"
    scanner = scan.get("scanner") or "—"
    profile = scan.get("profile") or "—"
    status = scan.get("status") or "—"
    scan_id = scan.get("id") or "—"
    created = scan.get("created_at")
    completed = scan.get("completed_at")

    lines = [
        f"# SecuraIQ Scan Report",
        "",
        f"- **Scan ID:** `{scan_id}`",
        f"- **Target:** `{target}`",
        f"- **Scanner:** {scanner}",
        f"- **Profile:** {profile}",
        f"- **Status:** {status}",
        f"- **Authorized:** {'yes' if scan.get('authorized') else 'no'}",
    ]
    if created:
        lines.append(f"- **Created:** {created}")
    if completed:
        lines.append(f"- **Completed:** {completed}")
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Open ports: **{summary.get('open_ports', '—')}**",
            f"- Findings created: **{summary.get('findings_created', summary.get('findings', len(findings)))}**",
            f"- Checked ports: **{summary.get('checked_ports', '—')}**",
            f"- Asset ID: `{summary.get('asset_id') or '—'}`",
            "",
            "## Findings",
            "",
        ]
    )
    if not findings:
        lines.append("_No findings recorded for this scan._")
    else:
        for i, f in enumerate(findings, 1):
            sev = (f.get("severity") or "info").upper()
            title = f.get("title") or "Untitled"
            cve = f.get("cve") or ""
            src = f.get("source") or ""
            extra = f" · {cve}" if cve else ""
            lines.append(f"{i}. **[{sev}]** {title}{extra}")
            if src:
                lines.append(f"   - Source: `{src}`")
            rem = (f.get("raw") or {}).get("remediation") if isinstance(f.get("raw"), dict) else None
            if rem:
                lines.append(f"   - Remediation: {rem}")
            lines.append("")

    arts = summary.get("artifacts") or []
    if arts:
        lines.extend(["## Evidence artifacts", ""])
        for a in arts:
            lines.append(f"- `{a}`")
        lines.append("")

    lines.extend(
        [
            "## Notes",
            "",
            "- Only scan systems you own or are authorized to test.",
            "- Private Windows ports 135/139/445 are down-ranked to info on RFC1918 networks.",
            f"- Generated at `{now()}`.",
            "",
        ]
    )
    return "\n".join(lines)


def write_scan_report(
    evidence_dir: Path,
    scan: dict[str, Any],
    *,
    findings: list[dict[str, Any]] | None = None,
) -> Path:
    """Write report.md into the scan evidence directory. Returns path."""
    evidence_dir = Path(evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = evidence_dir / "report.md"
    path.write_text(build_scan_report_md(scan, findings=findings), encoding="utf-8")
    return path


def findings_for_scan(user_id: str, scan_id: str) -> list[dict[str, Any]]:
    """Load vulnerability rows created by this scan_id (via raw_json)."""
    import json

    from app.db import get_conn, row_to_dict

    rows = get_conn().execute(
        "SELECT * FROM vulnerabilities WHERE user_id = ? ORDER BY created_at DESC LIMIT 500",
        (user_id,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        d = row_to_dict(row) or {}
        raw = d.get("raw_json") or "{}"
        if isinstance(raw, str):
            try:
                raw_obj = json.loads(raw)
            except Exception:
                raw_obj = {}
        else:
            raw_obj = raw if isinstance(raw, dict) else {}
        if str(raw_obj.get("scan_id") or "") == str(scan_id):
            d["raw"] = raw_obj
            out.append(d)
    return out
