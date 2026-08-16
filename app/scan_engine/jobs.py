"""Register scan_execute job handler with the in-process worker."""

from __future__ import annotations

from typing import Any

from app.jobs import register_job


@register_job("scan_execute")
async def handle_scan_execute(payload: dict[str, Any]) -> dict[str, Any]:
    from app.scan_engine.executor import execute_scan

    scan_id = (payload or {}).get("scan_id")
    if not scan_id:
        raise ValueError("scan_id required")
    return await execute_scan(str(scan_id))
