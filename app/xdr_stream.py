"""Background tasks that keep EDR detections close to real time.

CrowdStrike: hold open the Falcon Streaming API (true push — no public
webhook required on our side).

Sophos / SentinelOne / Defender: these vendors do not expose a Falcon-style
client-held NDJSON feed for detections. For a local-first tool the honest
substitute is a **near-real-time incremental poll** (default every 60s) that
reuses each connector's `fetch_detections()` and feeds new rows into the same
`ingest_detections` path. Full reconciliation still runs on the slower
`xdr_sync` job. True vendor→SecuraIQ push without polling remains available
via `POST /api/xdr/ingest` (and Wazuh/GitHub webhooks).

Honest gap: none of these paths have been exercised against a live tenant —
protocol/API-shape match only. Trial credentials required to prove them out.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.config import settings

_tasks: list[asyncio.Task] = []
_states: dict[str, dict[str, Any]] = {}

_MIN_BACKOFF_SEC = 5
_MAX_BACKOFF_SEC = 300
_POLL_VENDORS = ("sophos", "sentinelone", "defender")


def _blank(mode: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "connected": False,
        "last_ok_at": None,
        "last_event_at": None,
        "last_error": None,
        "attempts": 0,
    }


def status() -> dict[str, dict[str, Any]]:
    """Per-vendor streaming / near-realtime status for `/api/xdr/status`."""
    out: dict[str, dict[str, Any]] = {}
    for vendor, state in _states.items():
        out[vendor] = dict(state)
    # Stable keys even before start()
    for vendor, mode in (
        ("crowdstrike", "stream"),
        ("sophos", "near_realtime_poll"),
        ("sentinelone", "near_realtime_poll"),
        ("defender", "near_realtime_poll"),
    ):
        out.setdefault(vendor, _blank(mode))
    return out


def _set(vendor: str, **kwargs: Any) -> None:
    st = _states.setdefault(vendor, _blank("stream" if vendor == "crowdstrike" else "near_realtime_poll"))
    st.update(kwargs)


async def _run_crowdstrike() -> None:
    from app.connectors import crowdstrike as cs
    from app.xdr import ingest_detections

    _set("crowdstrike", mode="stream")
    backoff = _MIN_BACKOFF_SEC
    while True:
        if not cs.is_configured():
            _set("crowdstrike", connected=False)
            await asyncio.sleep(30)
            continue
        if not getattr(settings, "crowdstrike_streaming_enabled", True):
            _set("crowdstrike", connected=False, last_error="disabled via CROWDSTRIKE_STREAMING_ENABLED")
            await asyncio.sleep(60)
            continue
        try:
            _set("crowdstrike", last_error=None)
            async for item in cs.stream_events():
                if not _states.get("crowdstrike", {}).get("connected"):
                    _set("crowdstrike", connected=True, attempts=0)
                    backoff = _MIN_BACKOFF_SEC
                _set("crowdstrike", last_event_at=time.time(), last_ok_at=time.time())
                try:
                    ingest_detections([item], user_id="local")
                except Exception as exc:  # noqa: BLE001
                    _set("crowdstrike", last_error=f"ingest: {exc}")
            _set("crowdstrike", connected=False)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            attempts = int(_states.get("crowdstrike", {}).get("attempts") or 0) + 1
            _set("crowdstrike", connected=False, last_error=str(exc), attempts=attempts)
        await asyncio.sleep(backoff)
        backoff = min(_MAX_BACKOFF_SEC, backoff * 2)


def _poll_module(vendor: str):
    if vendor == "sophos":
        from app.connectors import sophos as m
    elif vendor == "sentinelone":
        from app.connectors import sentinelone as m
    elif vendor == "defender":
        from app.connectors import defender as m
    else:
        raise ValueError(f"No near-realtime poll module for {vendor}")
    return m


async def _run_near_realtime(vendor: str) -> None:
    """Tight poll loop — not a fake Falcon stream; labeled as near_realtime_poll."""
    from app.xdr import ingest_detections

    _set(vendor, mode="near_realtime_poll")
    while True:
        interval = max(15, int(getattr(settings, "xdr_near_realtime_interval_sec", 60) or 60))
        if not getattr(settings, "xdr_near_realtime_enabled", True):
            _set(vendor, connected=False, last_error="disabled via XDR_NEAR_REALTIME_ENABLED")
            await asyncio.sleep(60)
            continue
        try:
            mod = _poll_module(vendor)
        except Exception as exc:  # noqa: BLE001
            _set(vendor, connected=False, last_error=str(exc))
            await asyncio.sleep(60)
            continue
        if not mod.is_configured():
            _set(vendor, connected=False, last_error=None)
            await asyncio.sleep(30)
            continue
        try:
            items = await mod.fetch_detections(limit=100)
            _set(vendor, connected=True, last_ok_at=time.time(), last_error=None, attempts=0)
            if items:
                result = ingest_detections(items, user_id="local")
                if int(result.get("new") or 0) > 0:
                    _set(vendor, last_event_at=time.time())
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            attempts = int(_states.get(vendor, {}).get("attempts") or 0) + 1
            _set(vendor, connected=False, last_error=str(exc), attempts=attempts)
        await asyncio.sleep(interval)


def start() -> None:
    """Call once from FastAPI lifespan. Spawns one task per live path."""
    global _tasks
    if _tasks:
        return

    for vendor, mode in (
        ("crowdstrike", "stream"),
        ("sophos", "near_realtime_poll"),
        ("sentinelone", "near_realtime_poll"),
        ("defender", "near_realtime_poll"),
    ):
        _states.setdefault(vendor, _blank(mode))

    if getattr(settings, "crowdstrike_streaming_enabled", True):
        _tasks.append(asyncio.create_task(_run_crowdstrike(), name="xdr-stream-crowdstrike"))

    if getattr(settings, "xdr_near_realtime_enabled", True):
        for vendor in _POLL_VENDORS:
            _tasks.append(
                asyncio.create_task(_run_near_realtime(vendor), name=f"xdr-near-rt-{vendor}")
            )


async def stop() -> None:
    global _tasks
    for task in _tasks:
        task.cancel()
    for task in _tasks:
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
    _tasks = []
    for vendor in list(_states.keys()):
        _set(vendor, connected=False)
