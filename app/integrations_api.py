"""Live integration webhooks (GitHub, etc.)."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.auth import AuthUser
from app.commercial_api import require_user
from app.config import settings
from app.connectors.github_webhook import alerts_to_vuln_rows, verify_signature
from app.enterprise import create_vulnerability
from app.db import audit

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


@router.post("/github/webhook")
async def github_webhook(
    request: Request,
    x_github_event: Annotated[str | None, Header(alias="X-GitHub-Event")] = None,
    x_hub_signature_256: Annotated[str | None, Header(alias="X-Hub-Signature-256")] = None,
):
    """Ingest GitHub code scanning / Dependabot / secret scanning alerts."""
    secret = (settings.github_webhook_secret or "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="Set GITHUB_WEBHOOK_SECRET in Settings / .env")
    body = await request.body()
    if not verify_signature(body, x_hub_signature_256, secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event = (x_github_event or "").strip()
    if event == "ping":
        return {"ok": True, "event": "ping"}

    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    rows = alerts_to_vuln_rows(payload, event)
    if not rows:
        return {"ok": True, "event": event, "imported": 0, "note": "Event acknowledged — no vuln mapping"}

    # Webhook has no user session — attribute to bootstrap admin or local
    user_id = "local"
    if settings.auth_enabled:
        from app.db import get_conn

        row = get_conn().execute(
            "SELECT id FROM users WHERE role = 'admin' ORDER BY created_at LIMIT 1"
        ).fetchone()
        if row:
            user_id = row["id"]

    created = []
    for row in rows[:20]:
        created.append(create_vulnerability(user_id, row))
    audit("github_webhook", user_id, {"event": event, "count": len(created)})
    return {"ok": True, "event": event, "imported": len(created), "vulnerabilities": created[:10]}


@router.get("/github/status")
async def github_status(user: Annotated[AuthUser, Depends(require_user)]):
    configured = bool((settings.github_webhook_secret or "").strip())
    return {
        "configured": configured,
        "webhook_path": "/api/integrations/github/webhook",
        "events": ["code_scanning_alert", "dependabot_alert", "secret_scanning_alert", "ping"],
        "docs": "https://docs.github.com/en/webhooks",
    }
