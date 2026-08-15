"""XDR/EDR orchestration — pulls from configured endpoint vendors (Sophos,
CrowdStrike, SentinelOne, Microsoft Defender for Endpoint), normalizes their
alerts into one shape, dedupes against `xdr_events`, and — for new
critical/high findings — opens a real incident (via app.ops.create_incident,
same path human-created incidents use, so notifications/Slack/Teams alerts
already wired there fire for these too) or a vulnerability row for missing
patches (via app.enterprise.create_vulnerability).

Each vendor module is self-contained and only activates once its own
credentials are set (`is_configured()`); an unconfigured vendor is silently
skipped, never an error, so partial rollout (e.g. only Sophos configured) is
the expected steady state, not a degraded one.
"""

from __future__ import annotations

import json
from typing import Any

from app.config import settings
from app.db import get_conn, new_id, now

VENDORS = ("sophos", "crowdstrike", "sentinelone", "defender")


def _vendor_module(vendor: str):
    if vendor == "sophos":
        from app.connectors import sophos as m
    elif vendor == "crowdstrike":
        from app.connectors import crowdstrike as m
    elif vendor == "sentinelone":
        from app.connectors import sentinelone as m
    elif vendor == "defender":
        from app.connectors import defender as m
    else:
        raise ValueError(f"Unknown XDR vendor: {vendor}")
    return m


def status() -> dict[str, Any]:
    """Which vendors are configured/active — used by /api/xdr/status and the integrations catalog."""
    out = {}
    for v in VENDORS:
        m = _vendor_module(v)
        out[v] = {"configured": m.is_configured()}
    return out


def _upsert_event(item: dict[str, Any], user_id: str) -> tuple[dict[str, Any], bool]:
    """Insert if new; returns (row, is_new). Existing events are left alone
    (we don't overwrite analyst-modified status on a resync)."""
    c = get_conn()
    existing = c.execute(
        "SELECT * FROM xdr_events WHERE vendor = ? AND external_id = ?",
        (item["vendor"], item["external_id"]),
    ).fetchone()
    if existing:
        return dict(existing), False

    eid = new_id()
    ts = now()
    c.execute(
        """
        INSERT INTO xdr_events
        (id, vendor, external_id, kind, severity, host, title, status, raw_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)
        """,
        (
            eid,
            item["vendor"],
            item["external_id"],
            item.get("kind", "detection"),
            item.get("severity", "medium"),
            item.get("host", ""),
            item.get("title", ""),
            json.dumps(item.get("raw") or {}),
            ts,
            ts,
        ),
    )
    c.commit()
    row = c.execute("SELECT * FROM xdr_events WHERE id = ?", (eid,)).fetchone()
    result = dict(row)
    try:
        from app.realtime_bus import publish

        publish(
            type="xdr",
            vendor=item.get("vendor"),
            id=eid,
            severity=item.get("severity"),
            title=(item.get("title") or "")[:120],
        )
    except Exception:
        pass
    return result, True


def ingest_detections(
    items: list[dict[str, Any]],
    user_id: str = "local",
    *,
    auto_incidents: bool | None = None,
) -> dict[str, Any]:
    """Normalize + upsert push/webhook detections (lab or vendor inbound)."""
    do_auto = settings.xdr_auto_create_incidents if auto_incidents is None else auto_incidents
    new_count = 0
    created: list[dict[str, Any]] = []
    for raw in items:
        vendor = (raw.get("vendor") or "generic").strip().lower() or "generic"
        external_id = str(raw.get("external_id") or raw.get("id") or "").strip()
        if not external_id:
            continue
        item = {
            "vendor": vendor,
            "external_id": external_id,
            "kind": raw.get("kind") or "detection",
            "severity": (raw.get("severity") or "medium").lower(),
            "host": raw.get("host") or raw.get("agent") or "",
            "title": raw.get("title") or raw.get("rule") or "Inbound detection",
            "description": raw.get("description") or "",
            "raw": raw.get("raw") or raw,
        }
        row, is_new = _upsert_event(item, user_id)
        if not is_new:
            continue
        new_count += 1
        created.append(row)
        if not do_auto:
            continue
        if item.get("kind") == "patch_missing":
            from app.enterprise import create_vulnerability

            vuln = create_vulnerability(
                user_id,
                {
                    "title": item.get("title", "Missing patch"),
                    "severity": item.get("severity", "medium"),
                    "asset_name": item.get("host", ""),
                    "source": f"xdr:{vendor}",
                    "status": "open",
                    "raw": item.get("raw"),
                },
            )
            _link_vuln(row["id"], vuln["id"])
        elif item.get("severity") in ("critical", "high"):
            from app.ops import create_incident

            inc = create_incident(
                user_id,
                title=f"[{vendor}] {item.get('title', 'XDR detection')}",
                severity=item.get("severity", "high"),
                status="open",
                source=f"xdr:{vendor}",
                summary=item.get("description", "")
                + (f" | host={item.get('host')}" if item.get("host") else ""),
            )
            _link_incident(row["id"], inc["id"])
    if new_count:
        try:
            from app.realtime_bus import publish

            publish(type="xdr_batch", new=new_count, user_id=user_id)
        except Exception:
            pass
    return {"new": new_count, "total": len(items), "events": created[:20]}


def _link_incident(event_id: str, incident_id: str) -> None:
    c = get_conn()
    c.execute(
        "UPDATE xdr_events SET linked_incident_id = ?, updated_at = ? WHERE id = ?",
        (incident_id, now(), event_id),
    )
    c.commit()


def _link_vuln(event_id: str, vuln_id: str) -> None:
    c = get_conn()
    c.execute(
        "UPDATE xdr_events SET linked_vuln_id = ?, updated_at = ? WHERE id = ?",
        (vuln_id, now(), event_id),
    )
    c.commit()


async def sync_vendor(vendor: str, user_id: str = "local") -> dict[str, Any]:
    m = _vendor_module(vendor)
    if not m.is_configured():
        return {"vendor": vendor, "configured": False, "new": 0, "total": 0}

    items = await m.fetch_detections()
    new_count = 0
    for item in items:
        row, is_new = _upsert_event(item, user_id)
        if not is_new:
            continue
        new_count += 1
        if not settings.xdr_auto_create_incidents:
            continue
        if item.get("kind") == "patch_missing":
            from app.enterprise import create_vulnerability

            vuln = create_vulnerability(
                user_id,
                {
                    "title": item.get("title", "Missing patch"),
                    "severity": item.get("severity", "medium"),
                    "asset_name": item.get("host", ""),
                    "source": f"xdr:{vendor}",
                    "status": "open",
                    "raw": item.get("raw"),
                },
            )
            _link_vuln(row["id"], vuln["id"])
        elif item.get("severity") in ("critical", "high"):
            from app.ops import create_incident

            inc = create_incident(
                user_id,
                title=f"[{vendor}] {item.get('title', 'XDR detection')}",
                severity=item.get("severity", "high"),
                status="open",
                source=f"xdr:{vendor}",
                summary=item.get("description", "") + (f" | host={item.get('host')}" if item.get("host") else ""),
            )
            _link_incident(row["id"], inc["id"])

    # Defender is the only vendor with a distinct patch-compliance feed today.
    if vendor == "defender":
        try:
            patches = await m.fetch_missing_patches()
        except Exception:
            patches = []
        for item in patches:
            row, is_new = _upsert_event(item, user_id)
            if not is_new:
                continue
            new_count += 1
            if settings.xdr_auto_create_incidents:
                from app.enterprise import create_vulnerability

                vuln = create_vulnerability(
                    user_id,
                    {
                        "title": item.get("title", "Missing patch"),
                        "severity": item.get("severity", "medium"),
                        "asset_name": item.get("host", ""),
                        "source": f"xdr:{vendor}",
                        "status": "open",
                        "raw": item.get("raw"),
                    },
                )
                _link_vuln(row["id"], vuln["id"])
        items = items + patches

    return {"vendor": vendor, "configured": True, "new": new_count, "total": len(items)}


async def sync_all(user_id: str = "local") -> dict[str, Any]:
    results = []
    for v in VENDORS:
        try:
            results.append(await sync_vendor(v, user_id))
        except Exception as exc:
            results.append({"vendor": v, "configured": True, "error": str(exc), "new": 0, "total": 0})
    return {
        "results": results,
        "total_new": sum(r.get("new", 0) for r in results),
    }


def list_events(limit: int = 100, vendor: str | None = None, kind: str | None = None) -> list[dict[str, Any]]:
    c = get_conn()
    q = "SELECT * FROM xdr_events"
    conds, args = [], []
    if vendor:
        conds.append("vendor = ?")
        args.append(vendor)
    if kind:
        conds.append("kind = ?")
        args.append(kind)
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY created_at DESC LIMIT ?"
    args.append(max(1, min(limit, 500)))
    rows = [dict(r) for r in c.execute(q, args).fetchall()]
    for r in rows:
        try:
            r["raw"] = json.loads(r.get("raw_json") or "{}")
        except Exception:
            r["raw"] = {}
    return rows


def patch_compliance_summary() -> dict[str, Any]:
    """Aggregate missing-patch events by host and severity — the "is patching
    working" view. Populated once the Defender connector (or a future
    vendor's patch feed) is configured and synced at least once."""
    c = get_conn()
    rows = c.execute(
        "SELECT host, severity, COUNT(*) AS n FROM xdr_events WHERE kind = 'patch_missing' "
        "AND status = 'open' GROUP BY host, severity"
    ).fetchall()
    by_host: dict[str, dict[str, int]] = {}
    total = 0
    for r in rows:
        host = r["host"] or "unknown"
        by_host.setdefault(host, {"critical": 0, "high": 0, "medium": 0, "low": 0})
        sev = r["severity"] if r["severity"] in by_host[host] else "medium"
        by_host[host][sev] += r["n"]
        total += r["n"]
    return {
        "total_missing_patches": total,
        "hosts_with_gaps": len(by_host),
        "by_host": by_host,
    }
