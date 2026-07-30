"""ServiceNow connector — creates incidents via the Table API.

Requires SERVICENOW_INSTANCE_URL (e.g. https://yourinstance.service-now.com),
SERVICENOW_USERNAME, SERVICENOW_PASSWORD (a dedicated integration user with
the `incident` table's write role — not a personal login). Mirrors the same
pattern as app/commercial_ext.py::jira_create_issue.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


def is_configured() -> bool:
    return bool(
        settings.servicenow_instance_url and settings.servicenow_username and settings.servicenow_password
    )


async def create_incident(
    *, short_description: str, description: str, urgency: str = "2"
) -> dict[str, Any]:
    if not is_configured():
        raise ValueError(
            "ServiceNow not configured. Set SERVICENOW_INSTANCE_URL, SERVICENOW_USERNAME, "
            "SERVICENOW_PASSWORD in Settings/.env."
        )
    base = settings.servicenow_instance_url.rstrip("/")
    payload = {
        "short_description": short_description[:160],
        "description": description[:4000],
        "urgency": urgency,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            f"{base}/api/now/table/incident",
            json=payload,
            auth=(settings.servicenow_username, settings.servicenow_password),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
    if resp.status_code >= 400:
        raise ValueError(f"ServiceNow error {resp.status_code}: {resp.text[:400]}")
    data = resp.json().get("result", {})
    return {"ok": True, "number": data.get("number"), "sys_id": data.get("sys_id"), "raw": data}
