"""Wazuh SIEM orchestration — sync agents + alerts into SecuraIQ.

Alerts land in ``xdr_events`` with vendor=``wazuh`` (same SOC feed as EDR).
Agent inventory is stored in ``wazuh_agents`` for the SOC panel.
"""

from __future__ import annotations

import json
from typing import Any

from app.config import settings
from app.connectors import wazuh as wazuh_conn
from app.db import get_conn, new_id, now


def status() -> dict[str, Any]:
    configured = wazuh_conn.is_configured()
    return {
        "configured": configured,
        "indexer_configured": wazuh_conn.indexer_configured(),
        "base_url": (settings.wazuh_base_url or "").rstrip("/") if configured else "",
        "verify_ssl": bool(settings.wazuh_verify_ssl),
    }


def ensure_schema() -> None:
    c = get_conn()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS wazuh_agents (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL DEFAULT '',
            ip TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT '',
            os TEXT NOT NULL DEFAULT '',
            version TEXT NOT NULL DEFAULT '',
            group_name TEXT NOT NULL DEFAULT '',
            last_keep_alive TEXT NOT NULL DEFAULT '',
            raw_json TEXT NOT NULL DEFAULT '{}',
            updated_at REAL NOT NULL
        )
        """
    )
    c.commit()


def _upsert_agent(item: dict[str, Any]) -> bool:
    """Returns True if inserted, False if updated/skipped."""
    ensure_schema()
    aid = str(item.get("agent_id") or "")
    if not aid:
        return False
    c = get_conn()
    ts = now()
    fields = (
        item.get("name") or "",
        item.get("ip") or "",
        item.get("status") or "",
        item.get("os") or "",
        item.get("version") or "",
        item.get("group") or "",
        item.get("last_keep_alive") or "",
        json.dumps(item.get("raw") or item),
        ts,
    )
    existing = c.execute("SELECT id FROM wazuh_agents WHERE agent_id = ?", (aid,)).fetchone()
    if existing:
        c.execute(
            """
            UPDATE wazuh_agents SET name=?, ip=?, status=?, os=?, version=?, group_name=?,
            last_keep_alive=?, raw_json=?, updated_at=? WHERE agent_id=?
            """,
            (*fields, aid),
        )
        c.commit()
        return False
    c.execute(
        """
        INSERT INTO wazuh_agents
        (id, agent_id, name, ip, status, os, version, group_name, last_keep_alive, raw_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (new_id(), aid, *fields),
    )
    c.commit()
    return True


def list_agents(limit: int = 100) -> list[dict[str, Any]]:
    ensure_schema()
    rows = get_conn().execute(
        "SELECT * FROM wazuh_agents ORDER BY updated_at DESC LIMIT ?",
        (max(1, min(limit, 500)),),
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
    if not wazuh_conn.is_configured():
        return {
            "configured": False,
            "agents_new": 0,
            "agents_total": 0,
            "alerts_new": 0,
            "alerts_total": 0,
        }

    from app.xdr import _link_incident, _upsert_event

    agents = await wazuh_conn.fetch_agents()
    agents_new = sum(1 for a in agents if _upsert_agent(a))

    detections = await wazuh_conn.fetch_detections()
    alerts_new = 0
    for item in detections:
        row, is_new = _upsert_event(item, user_id)
        if not is_new:
            continue
        alerts_new += 1
        if settings.xdr_auto_create_incidents and item.get("severity") in ("critical", "high"):
            from app.ops import create_incident

            inc = create_incident(
                user_id,
                title=f"[SIEM] {item.get('title', 'SecuraIQ SIEM alert')}",
                severity=item.get("severity", "high"),
                status="open",
                source="siem:wazuh",
                summary=item.get("description", "")
                + (f" | host={item.get('host')}" if item.get("host") else ""),
            )
            _link_incident(row["id"], inc["id"])

    out = {
        "configured": True,
        "agents_new": agents_new,
        "agents_total": len(agents),
        "alerts_new": alerts_new,
        "alerts_total": len(detections),
        "indexer": wazuh_conn.indexer_configured(),
    }
    try:
        from app.realtime_bus import publish

        publish(type="siem", source="wazuh", alerts_new=alerts_new, agents_new=agents_new)
    except Exception:
        pass
    return out
