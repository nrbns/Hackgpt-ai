"""Outbound webhooks for automation (n8n / Temporal / Slack bridges)."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.db import audit, get_conn, new_id, now, row_to_dict


def ensure_webhook_schema() -> None:
    c = get_conn()
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS webhooks (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            events TEXT NOT NULL DEFAULT '["*"]',
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at REAL NOT NULL
        );
        """
    )
    c.commit()


def create_webhook(user_id: str, *, name: str, url: str, events: list[str] | None = None) -> dict[str, Any]:
    ensure_webhook_schema()
    wid = new_id()
    get_conn().execute(
        """
        INSERT INTO webhooks (id, user_id, name, url, events, enabled, created_at)
        VALUES (?, ?, ?, ?, ?, 1, ?)
        """,
        (wid, user_id, name.strip()[:120], url.strip()[:500], json.dumps(events or ["*"]), now()),
    )
    get_conn().commit()
    audit("webhook_create", user_id, {"id": wid, "name": name})
    return get_webhook(user_id, wid)  # type: ignore[return-value]


def get_webhook(user_id: str, webhook_id: str) -> dict[str, Any] | None:
    ensure_webhook_schema()
    row = get_conn().execute(
        "SELECT * FROM webhooks WHERE id = ? AND user_id = ?", (webhook_id, user_id)
    ).fetchone()
    return row_to_dict(row)


def list_webhooks(user_id: str) -> list[dict[str, Any]]:
    ensure_webhook_schema()
    rows = get_conn().execute(
        "SELECT * FROM webhooks WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
    ).fetchall()
    out = []
    for r in rows:
        d = row_to_dict(r)
        if d:
            try:
                d["events"] = json.loads(d.get("events") or "[]")
            except json.JSONDecodeError:
                d["events"] = ["*"]
            out.append(d)
    return out


def delete_webhook(user_id: str, webhook_id: str) -> bool:
    ensure_webhook_schema()
    cur = get_conn().execute(
        "DELETE FROM webhooks WHERE id = ? AND user_id = ?", (webhook_id, user_id)
    )
    get_conn().commit()
    return bool(cur.rowcount)


async def dispatch_webhooks(user_id: str, event: str, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_webhook_schema()
    hooks = [h for h in list_webhooks(user_id) if h.get("enabled")]
    sent = 0
    errors: list[str] = []
    body = {"event": event, "payload": payload, "source": "securaiq"}
    async with httpx.AsyncClient(timeout=8.0) as client:
        for h in hooks:
            evs = h.get("events") or ["*"]
            if "*" not in evs and event not in evs:
                continue
            try:
                r = await client.post(h["url"], json=body)
                if r.status_code >= 400:
                    errors.append(f"{h.get('name')}: HTTP {r.status_code}")
                else:
                    sent += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{h.get('name')}: {exc}")
    audit("webhook_dispatch", user_id, {"event": event, "sent": sent, "errors": len(errors)})
    return {"sent": sent, "errors": errors[:10]}
