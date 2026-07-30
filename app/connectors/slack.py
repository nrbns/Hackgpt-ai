"""Slack connector — outbound alerts via an Incoming Webhook.

No OAuth app install required: create a Slack "Incoming Webhook" for a
channel (api.slack.com/messaging/webhooks), set SLACK_WEBHOOK_URL, and
SecuraIQ pushes critical-vulnerability and incident alerts there
automatically (see app/enterprise.py::create_vulnerability, app/ops.py::create_incident).
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


def is_configured() -> bool:
    return bool(settings.slack_webhook_url)


async def send_message(text: str, *, blocks: list[dict] | None = None) -> bool:
    if not is_configured():
        return False
    body: dict[str, Any] = {"text": text}
    if blocks:
        body["blocks"] = blocks
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(settings.slack_webhook_url, json=body)
            return resp.status_code < 400
    except Exception:
        return False
