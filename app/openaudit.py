"""Open-AudIT orchestration — sync discovered devices into SecuraIQ assets."""

from __future__ import annotations

import json
from typing import Any

from app.config import settings
from app.connectors import openaudit as oa_conn
from app.db import get_conn, new_id, now
from app.enterprise import create_asset, list_assets


def status() -> dict[str, Any]:
    ensure_schema()
    configured = oa_conn.is_configured()
    cached = 0
    try:
        row = get_conn().execute("SELECT COUNT(*) AS n FROM openaudit_devices").fetchone()
        cached = int(row["n"] if row else 0)
    except Exception:
        cached = 0
    return {
        "configured": configured,
        "base_url": (settings.openaudit_base_url or "").rstrip("/") if configured else "",
        "api_root": oa_conn.api_root() if configured else "",
        "verify_ssl": bool(settings.openaudit_verify_ssl),
        "devices_cached": cached,
    }


def ensure_schema() -> None:
    c = get_conn()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS openaudit_devices (
            id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL DEFAULT '',
            hostname TEXT NOT NULL DEFAULT '',
            ip TEXT NOT NULL DEFAULT '',
            type TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT '',
            os TEXT NOT NULL DEFAULT '',
            domain TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            asset_id TEXT NOT NULL DEFAULT '',
            raw_json TEXT NOT NULL DEFAULT '{}',
            updated_at REAL NOT NULL
        )
        """
    )
    c.commit()


def _map_asset_type(oa_type: str) -> str:
    t = (oa_type or "").lower()
    if any(x in t for x in ("server", "virtual", "hypervisor", "vm")):
        return "server"
    if any(x in t for x in ("computer", "workstation", "laptop", "desktop", "endpoint")):
        return "endpoint"
    if any(x in t for x in ("database", "sql")):
        return "database"
    if any(x in t for x in ("router", "switch", "firewall", "access point", "network")):
        return "other"
    if "printer" in t:
        return "other"
    return "server" if t else "other"


def _upsert_device(item: dict[str, Any], user_id: str) -> tuple[bool, str]:
    """Returns (inserted, asset_id)."""
    ensure_schema()
    did = str(item.get("device_id") or "")
    if not did:
        return False, ""
    c = get_conn()
    ts = now()
    hostname = (item.get("hostname") or "").strip()
    ip = (item.get("ip") or "").strip()
    name = (item.get("name") or "").strip() or did
    if hostname and ip:
        name = f"{hostname} ({ip})"
    elif hostname:
        name = hostname
    elif ip:
        name = ip
    notes = (
        f"openaudit_id={did}\n"
        f"ip={item.get('ip') or ''}\n"
        f"hostname={item.get('hostname') or ''}\n"
        f"os={item.get('os') or ''}\n"
        f"domain={item.get('domain') or ''}\n"
        f"oa_type={item.get('type') or ''}\n"
        f"{item.get('description') or ''}"
    ).strip()
    existing = c.execute("SELECT id, asset_id FROM openaudit_devices WHERE device_id = ?", (did,)).fetchone()
    asset_id = (existing["asset_id"] if existing else "") or ""

    if not asset_id:
        for a in list_assets(user_id):
            if f"openaudit_id={did}" in (a.get("notes") or ""):
                asset_id = a["id"]
                break
            if (a.get("name") or "").strip().lower() == name.strip().lower():
                asset_id = a["id"]
                break
    if not asset_id:
        created = create_asset(
            user_id,
            name,
            asset_type=_map_asset_type(str(item.get("type") or "")),
            criticality="high" if (item.get("status") or "").lower() in {"production", "prod"} else "medium",
            owner="Inventory",
            notes=notes,
        )
        asset_id = created.get("id") or ""
    else:
        c.execute(
            "UPDATE assets SET name=?, asset_type=?, notes=?, updated_at=? WHERE id=? AND user_id=?",
            (name, _map_asset_type(str(item.get("type") or "")), notes, ts, asset_id, user_id),
        )

    fields = (
        name,
        item.get("hostname") or "",
        item.get("ip") or "",
        item.get("type") or "",
        item.get("status") or "",
        item.get("os") or "",
        item.get("domain") or "",
        item.get("description") or "",
        asset_id,
        json.dumps(item.get("raw") or item, default=str),
        ts,
    )
    inserted = False
    if existing:
        c.execute(
            """
            UPDATE openaudit_devices SET name=?, hostname=?, ip=?, type=?, status=?, os=?,
            domain=?, description=?, asset_id=?, raw_json=?, updated_at=? WHERE device_id=?
            """,
            (*fields, did),
        )
    else:
        c.execute(
            """
            INSERT INTO openaudit_devices
            (id, device_id, name, hostname, ip, type, status, os, domain, description, asset_id, raw_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (new_id(), did, *fields),
        )
        inserted = True
    c.commit()
    return inserted, asset_id


def list_devices(limit: int = 100) -> list[dict[str, Any]]:
    ensure_schema()
    rows = get_conn().execute(
        "SELECT * FROM openaudit_devices ORDER BY updated_at DESC LIMIT ?",
        (max(1, min(500, int(limit))),),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["raw"] = json.loads(d.get("raw_json") or "{}")
        except Exception:
            d["raw"] = {}
        out.append(d)
    return out


async def sync(user_id: str = "local") -> dict[str, Any]:
    if not oa_conn.is_configured():
        return {"configured": False, "devices_new": 0, "devices_total": 0, "assets_linked": 0, "networks": 0}

    devices = await oa_conn.fetch_devices()
    new_count = 0
    linked = 0
    for item in devices:
        inserted, asset_id = _upsert_device(item, user_id)
        if inserted:
            new_count += 1
        if asset_id:
            linked += 1
    networks = await oa_conn.fetch_networks()
    out = {
        "configured": True,
        "devices_new": new_count,
        "devices_total": len(devices),
        "assets_linked": linked,
        "networks": len(networks),
    }
    try:
        from app.realtime_bus import publish

        publish(type="inventory", source="openaudit", devices_new=new_count, devices_total=len(devices), assets_linked=linked)
        publish(type="asset", source="inventory", count=linked)
    except Exception:
        pass
    return out
