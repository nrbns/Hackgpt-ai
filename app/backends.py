"""Reachability checks for local model backends."""

from __future__ import annotations

import httpx

from app.config import settings


async def openai_compat_reachable() -> bool:
    url = f"{settings.openai_compat_base_url.rstrip('/')}/models"
    headers = {"Authorization": f"Bearer {settings.openai_compat_api_key}"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            return (await client.get(url, headers=headers)).status_code == 200
    except httpx.HTTPError:
        return False
