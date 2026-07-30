"""Human-in-the-loop approval codes for high-impact / destructive actions.

Was genuinely only "partial" per docs/launch-readiness.md: `POST
/api/workspace/reset` required a client-side JS `confirm()` dialog and a
`confirm: true` boolean in the same request — which is not human approval,
it's a single blind call a compromised session/script can send just as
easily as a person clicking a button.

This adds a real two-step flow: request a code (delivered out-of-band via
the in-app notification feed, not returned in the request-code API
response), then submit that code with the actual destructive call. An
attacker with a stolen session token still can't complete the action without
also reading the notification.
"""

from __future__ import annotations

import secrets
from typing import Any

from app.db import get_conn, new_id, now, row_to_dict

CODE_TTL_SEC = 300  # 5 minutes


def request_approval(user_id: str, action: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    code = f"{secrets.randbelow(1_000_000):06d}"
    aid = new_id()
    t = now()
    c = get_conn()
    c.execute(
        "INSERT INTO action_approvals (id, user_id, action, detail_json, code, created_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (aid, user_id, action, __import__("json").dumps(detail or {}), code, t, t + CODE_TTL_SEC),
    )
    c.commit()

    from app.notifications import notify

    notify(
        user_id,
        "system",
        f"Confirmation code for {action.replace('_', ' ')}",
        f"Code: {code} — expires in {CODE_TTL_SEC // 60} minutes. "
        "Enter it to complete this action. If you didn't request this, ignore it and the code will expire unused.",
    )
    return {"requested": True, "action": action, "expires_in_sec": CODE_TTL_SEC}


def verify_and_consume(user_id: str, action: str, code: str) -> bool:
    if not code:
        return False
    c = get_conn()
    row = c.execute(
        "SELECT * FROM action_approvals WHERE user_id = ? AND action = ? AND code = ? "
        "AND consumed_at IS NULL ORDER BY created_at DESC LIMIT 1",
        (user_id, action, code.strip()),
    ).fetchone()
    d = row_to_dict(row)
    if not d:
        return False
    if now() > float(d["expires_at"]):
        return False
    c.execute("UPDATE action_approvals SET consumed_at = ? WHERE id = ?", (now(), d["id"]))
    c.commit()
    return True
