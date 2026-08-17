"""Local realtime archive — keep scan evidence when clearing live workspace.

Prototype rule: never throw away completed scan reports/evidence. Clear moves
them under ``data/archive/`` and realtime clients get an ``archive`` event.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from app.config import settings
from app.db import get_conn, now, row_to_dict


def data_root() -> Path:
    return Path(settings.data_dir)


def evidence_root() -> Path:
    return data_root() / "evidence" / "scans"


def archive_root() -> Path:
    return data_root() / "archive" / "scans"


def ensure_data_layout() -> dict[str, str]:
    """Create persistent dirs used by scans, evidence, and archive."""
    paths = {
        "data": data_root(),
        "evidence": evidence_root(),
        "archive": archive_root(),
        "uploads": data_root() / "uploads",
        "kpi_snaps": data_root() / "kpi_snaps",
        "chroma": Path(settings.chroma_persist_dir),
    }
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    return {k: str(v) for k, v in paths.items()}


def _safe_name(value: str) -> str:
    raw = (value or "item").strip()
    out = "".join(ch if ch.isalnum() or ch in "-._" else "_" for ch in raw)
    return (out or "item")[:80]


def archive_user_scans(user_id: str) -> dict[str, Any]:
    """Copy each scan's evidence + JSON manifest into data/archive before wipe."""
    from app.scan_engine.models import ensure_scans_schema, evidence_root as scan_evidence_root

    ensure_scans_schema()
    ensure_data_layout()
    c = get_conn()
    rows = c.execute(
        "SELECT * FROM scans WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    batch_dir = archive_root() / f"{_safe_name(user_id)}_{stamp}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    archived: list[dict[str, Any]] = []
    for row in rows:
        scan = row_to_dict(row) or {}
        sid = str(scan.get("id") or "")
        if not sid:
            continue
        src = Path(scan.get("evidence_dir") or "") if scan.get("evidence_dir") else scan_evidence_root(sid)
        dest = batch_dir / sid
        try:
            if src.exists():
                if dest.exists():
                    shutil.rmtree(dest, ignore_errors=True)
                shutil.copytree(src, dest)
            else:
                dest.mkdir(parents=True, exist_ok=True)
            meta = {
                "scan_id": sid,
                "user_id": user_id,
                "target": scan.get("target"),
                "scanner": scan.get("scanner"),
                "profile": scan.get("profile"),
                "status": scan.get("status"),
                "summary": scan.get("summary_json"),
                "created_at": scan.get("created_at"),
                "completed_at": scan.get("completed_at"),
                "archived_at": now(),
                "evidence_dir": str(dest),
            }
            try:
                if isinstance(meta["summary"], str):
                    meta["summary"] = json.loads(meta["summary"] or "{}")
            except Exception:
                meta["summary"] = {}
            (dest / "archive_meta.json").write_text(
                json.dumps(meta, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            archived.append(
                {
                    "scan_id": sid,
                    "target": scan.get("target"),
                    "scanner": scan.get("scanner"),
                    "status": scan.get("status"),
                    "path": str(dest),
                    "has_report": (dest / "report.md").is_file(),
                    "has_pdf": (dest / "report.pdf").is_file(),
                }
            )
        except Exception as exc:
            archived.append({"scan_id": sid, "error": str(exc)})

    manifest = {
        "user_id": user_id,
        "archived_at": now(),
        "batch_dir": str(batch_dir),
        "count": len(archived),
        "scans": archived,
    }
    (batch_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    try:
        from app.realtime_bus import publish

        publish(
            type="archive",
            user_id=user_id,
            count=len(archived),
            batch_dir=str(batch_dir),
            status="saved",
        )
    except Exception:
        pass

    return {
        "ok": True,
        "batch_dir": str(batch_dir),
        "archived_count": len(archived),
        "scans": archived,
    }


def list_archives(user_id: str, *, limit: int = 40) -> list[dict[str, Any]]:
    """List archived scan report cards for Reports / prototype demos."""
    ensure_data_layout()
    root = archive_root()
    if not root.is_dir():
        return []
    items: list[dict[str, Any]] = []
    batches = sorted(
        [p for p in root.iterdir() if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    uid = (user_id or "").strip()
    for batch in batches:
        if uid and uid != "local" and not batch.name.startswith(f"{_safe_name(uid)}_"):
            # Still allow local open-mode archives
            if not batch.name.startswith("local_"):
                continue
        for scan_dir in sorted(batch.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if not scan_dir.is_dir() or scan_dir.name.startswith("."):
                continue
            meta_path = scan_dir / "archive_meta.json"
            meta: dict[str, Any] = {}
            if meta_path.is_file():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    meta = {}
            if uid and meta.get("user_id") and meta.get("user_id") not in {uid, "local"}:
                continue
            sid = meta.get("scan_id") or scan_dir.name
            target = meta.get("target") or "target"
            scanner = meta.get("scanner") or "scan"
            title = f"Archive - {target} ({scanner})"
            if (scan_dir / "report.md").is_file():
                items.append(
                    {
                        "id": f"archive-md-{sid}",
                        "title": title,
                        "href": f"/api/archive/scans/{sid}/report",
                        "kind": "archive",
                        "scan_id": sid,
                        "created_at": meta.get("archived_at") or meta.get("created_at"),
                        "path": str(scan_dir),
                    }
                )
            if (scan_dir / "report.pdf").is_file():
                items.append(
                    {
                        "id": f"archive-pdf-{sid}",
                        "title": f"{title} (PDF)",
                        "href": f"/api/archive/scans/{sid}/report.pdf",
                        "kind": "archive-pdf",
                        "scan_id": sid,
                        "created_at": meta.get("archived_at") or meta.get("created_at"),
                        "path": str(scan_dir),
                    }
                )
            if len(items) >= limit:
                return items[:limit]
    return items[:limit]


def find_archived_scan(scan_id: str) -> Path | None:
    ensure_data_layout()
    sid = (scan_id or "").strip()
    if not sid:
        return None
    root = archive_root()
    if not root.is_dir():
        return None
    for batch in root.iterdir():
        if not batch.is_dir():
            continue
        candidate = batch / sid
        if candidate.is_dir():
            return candidate
    return None


def prototype_status() -> dict[str, Any]:
    """Compact readiness signal for Mission Control / health."""
    layout = ensure_data_layout()
    zero = bool(getattr(settings, "workspace_zero_start", False))
    auth = bool(getattr(settings, "auth_enabled", False))
    evidence_n = 0
    archive_n = 0
    try:
        evidence_n = sum(1 for _ in evidence_root().glob("*") if _.is_dir())
    except Exception:
        pass
    try:
        archive_n = sum(1 for _ in archive_root().glob("*") if _.is_dir())
    except Exception:
        pass
    return {
        "ok": True,
        "data_persists": (not zero) or auth,
        "workspace_zero_start": zero,
        "auth_enabled": auth,
        "realtime": True,
        "paths": layout,
        "live_evidence_scans": evidence_n,
        "archive_batches": archive_n,
        "hint": (
            "Data kept across restarts · clear moves scans to data/archive"
            if (not zero) or auth
            else "WORKSPACE_ZERO_START=true will wipe workspace on boot — set false for prototype"
        ),
    }
