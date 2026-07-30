"""Microsoft Teams connector — outbound alerts via an Incoming Webhook
connector on a channel. Set TEAMS_WEBHOOK_URL to enable.
"""

from __future__ import annotations

import httpx

from app.config import settings

# Teams' classic Incoming Webhook still expects the O365 "MessageCard" shape.
# (Adaptive Cards via Workflows is the newer path but requires a Power
# Automate flow per-tenant — MessageCard needs nothing beyond the webhook URL.)
_THEME_COLOR = "D93025"


def is_configured() -> bool:
    return bool(settings.teams_webhook_url)


async def send_message(title: str, text: str) -> bool:
    if not is_configured():
        return False
    body = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "summary": title,
        "themeColor": _THEME_COLOR,
        "title": title,
        "text": text,
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(settings.teams_webhook_url, json=body)
            return resp.status_code < 400
    except Exception:
        return False
