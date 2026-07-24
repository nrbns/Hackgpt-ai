"""Engagements, chats, messages, memories."""

from __future__ import annotations

import json
from typing import Any

from app.db import audit, get_conn, new_id, now, row_to_dict


def create_engagement(user_id: str, name: str, scope_notes: str = "") -> dict[str, Any]:
    eid = new_id()
    t = now()
    c = get_conn()
    c.execute(
        "INSERT INTO engagements (id, user_id, name, scope_notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (eid, user_id, (name or "Engagement").strip(), scope_notes or "", t, t),
    )
    c.commit()
    audit("engagement_create", user_id, {"id": eid, "name": name})
    return get_engagement(user_id, eid)  # type: ignore[return-value]


def list_engagements(user_id: str) -> list[dict[str, Any]]:
    c = get_conn()
    rows = c.execute(
        "SELECT * FROM engagements WHERE user_id = ? ORDER BY updated_at DESC",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_engagement(user_id: str, engagement_id: str) -> dict[str, Any] | None:
    c = get_conn()
    row = c.execute(
        "SELECT * FROM engagements WHERE id = ? AND user_id = ?",
        (engagement_id, user_id),
    ).fetchone()
    return row_to_dict(row)


def update_engagement(user_id: str, engagement_id: str, name: str | None = None, scope_notes: str | None = None) -> dict[str, Any] | None:
    eng = get_engagement(user_id, engagement_id)
    if not eng:
        return None
    c = get_conn()
    c.execute(
        "UPDATE engagements SET name = ?, scope_notes = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (
            name if name is not None else eng["name"],
            scope_notes if scope_notes is not None else eng["scope_notes"],
            now(),
            engagement_id,
            user_id,
        ),
    )
    c.commit()
    return get_engagement(user_id, engagement_id)


def create_chat(
    user_id: str,
    title: str = "New chat",
    mode: str = "default",
    engagement_id: str | None = None,
) -> dict[str, Any]:
    cid = new_id()
    t = now()
    c = get_conn()
    if engagement_id and not get_engagement(user_id, engagement_id):
        engagement_id = None
    c.execute(
        "INSERT INTO chats (id, engagement_id, user_id, title, mode, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (cid, engagement_id, user_id, (title or "New chat")[:120], mode or "default", t, t),
    )
    c.commit()
    audit("chat_create", user_id, {"id": cid, "engagement_id": engagement_id})
    return get_chat(user_id, cid)  # type: ignore[return-value]


def list_chats(user_id: str, engagement_id: str | None = None) -> list[dict[str, Any]]:
    c = get_conn()
    if engagement_id:
        rows = c.execute(
            "SELECT * FROM chats WHERE user_id = ? AND engagement_id = ? ORDER BY updated_at DESC",
            (user_id, engagement_id),
        ).fetchall()
    else:
        rows = c.execute(
            "SELECT * FROM chats WHERE user_id = ? ORDER BY updated_at DESC LIMIT 100",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_chat(user_id: str, chat_id: str) -> dict[str, Any] | None:
    c = get_conn()
    row = c.execute(
        "SELECT * FROM chats WHERE id = ? AND user_id = ?",
        (chat_id, user_id),
    ).fetchone()
    return row_to_dict(row)


def append_message(user_id: str, chat_id: str, role: str, content: str) -> dict[str, Any] | None:
    chat = get_chat(user_id, chat_id)
    if not chat:
        return None
    mid = new_id()
    t = now()
    c = get_conn()
    c.execute(
        "INSERT INTO messages (id, chat_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
        (mid, chat_id, role, content, t),
    )
    title = chat["title"]
    if title in {"New chat", "Untitled"} and role == "user":
        title = (content.strip().split("\n")[0] or title)[:80]
    c.execute(
        "UPDATE chats SET title = ?, updated_at = ? WHERE id = ?",
        (title, t, chat_id),
    )
    if chat.get("engagement_id"):
        c.execute(
            "UPDATE engagements SET updated_at = ? WHERE id = ?",
            (t, chat["engagement_id"]),
        )
    c.commit()
    return {"id": mid, "chat_id": chat_id, "role": role, "content": content, "created_at": t}


def list_messages(user_id: str, chat_id: str, limit: int = 200) -> list[dict[str, Any]]:
    if not get_chat(user_id, chat_id):
        return []
    c = get_conn()
    rows = c.execute(
        "SELECT * FROM messages WHERE chat_id = ? ORDER BY created_at ASC LIMIT ?",
        (chat_id, max(1, min(limit, 500))),
    ).fetchall()
    return [dict(r) for r in rows]


def delete_chat(user_id: str, chat_id: str) -> bool:
    if not get_chat(user_id, chat_id):
        return False
    c = get_conn()
    c.execute("DELETE FROM chats WHERE id = ? AND user_id = ?", (chat_id, user_id))
    c.commit()
    audit("chat_delete", user_id, {"id": chat_id})
    return True


def set_memory(user_id: str, engagement_id: str, key: str, value: str) -> dict[str, Any] | None:
    if not get_engagement(user_id, engagement_id):
        return None
    key = (key or "").strip()[:120]
    if not key:
        return None
    c = get_conn()
    mid = new_id()
    t = now()
    c.execute(
        "INSERT INTO memories (id, engagement_id, key, value, created_at) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(engagement_id, key) DO UPDATE SET value = excluded.value, created_at = excluded.created_at",
        (mid, engagement_id, key, value, t),
    )
    c.commit()
    audit("memory_set", user_id, {"engagement_id": engagement_id, "key": key})
    return {"engagement_id": engagement_id, "key": key, "value": value}


def list_memories(user_id: str, engagement_id: str) -> list[dict[str, Any]]:
    if not get_engagement(user_id, engagement_id):
        return []
    c = get_conn()
    rows = c.execute(
        "SELECT key, value, created_at FROM memories WHERE engagement_id = ? ORDER BY key",
        (engagement_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def memory_context(user_id: str, engagement_id: str | None) -> str:
    if not engagement_id:
        return ""
    if user_id != "local" and not get_engagement(user_id, engagement_id):
        return ""
    return memory_context_raw(engagement_id)


def memory_context_raw(engagement_id: str) -> str:
    c = get_conn()
    rows = c.execute(
        "SELECT key, value FROM memories WHERE engagement_id = ? ORDER BY key LIMIT 40",
        (engagement_id,),
    ).fetchall()
    if not rows:
        return ""
    lines = ["## Engagement memory"]
    for m in rows:
        lines.append(f"- **{m['key']}**: {m['value']}")
    return "\n".join(lines)


def list_audit(limit: int = 100) -> list[dict[str, Any]]:
    c = get_conn()
    rows = c.execute(
        "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?",
        (max(1, min(limit, 500)),),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["detail"] = json.loads(d.get("detail") or "{}")
        except Exception:
            pass
        out.append(d)
    return out
