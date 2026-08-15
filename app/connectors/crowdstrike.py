"""CrowdStrike Falcon connector — pulls Detections via the Falcon REST API,
and can optionally hold open the Falcon Streaming API for genuine real-time
push (see `stream_events` below) instead of waiting for the next poll tick.

Setup (Falcon console > Support and resources > API Clients and Keys):
  1. Create an OAuth2 API client with the "Detections: Read" scope (add
     "Event streams: Read" too if you want live streaming, not just polling).
  2. Set CROWDSTRIKE_CLIENT_ID / CROWDSTRIKE_CLIENT_SECRET in Settings/.env.
  3. CROWDSTRIKE_BASE_URL defaults to the US-1 cloud (api.crowdstrike.com) —
     change it for EU-1/US-2/US-GOV-1 tenants (see Falcon API docs).

Auth flow (OAuth2 client credentials):
  POST {base}/oauth2/token
  -> GET  {base}/detects/queries/detects/v1   (recent detection IDs)
  -> POST {base}/detects/entities/summaries/GET/v1   (hydrate IDs to full detections)

Streaming flow (Falcon Streaming API v2 — see
https://falconpy.io/Service-Collections/Event-Streams.html and
https://www.falconpy.io/Usage/Streaming-Data.html for the reference this
follows): discover a feed URL + session token, connect to it as a
newline-delimited-JSON HTTP stream, and refresh the session before it
expires (default every ~25-30 min) or the feed drops. **Not exercised
against a live tenant** — this implementation matches CrowdStrike's public
API docs, but "matches the docs" isn't the same as "verified working."
Test against a real (ideally trial) Falcon tenant before relying on it.
"""

from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator

import httpx

from app.config import settings

_cache: dict[str, Any] = {"token": None, "expires": 0.0}


def is_configured() -> bool:
    return bool(settings.crowdstrike_client_id and settings.crowdstrike_client_secret)


async def _access_token(client: httpx.AsyncClient) -> str:
    now = time.time()
    if _cache["token"] and _cache["expires"] > now + 30:
        return _cache["token"]
    base = settings.crowdstrike_base_url.rstrip("/")
    resp = await client.post(
        f"{base}/oauth2/token",
        data={
            "client_id": settings.crowdstrike_client_id,
            "client_secret": settings.crowdstrike_client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.status_code >= 400:
        raise ValueError(f"CrowdStrike token error {resp.status_code}: {resp.text[:300]}")
    tok = resp.json()
    _cache.update(token=tok["access_token"], expires=now + int(tok.get("expires_in", 1700)))
    return _cache["token"]


def _normalize_severity(score: int | None) -> str:
    # Falcon detections carry a 0-100 max_severity score, not a label.
    s = score or 0
    if s >= 80:
        return "critical"
    if s >= 60:
        return "high"
    if s >= 30:
        return "medium"
    return "low"


async def fetch_detections(limit: int = 100) -> list[dict[str, Any]]:
    """Fetch recent CrowdStrike Falcon detections, normalized for XDR ingestion."""
    if not is_configured():
        return []
    base = settings.crowdstrike_base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=20.0) as client:
        token = await _access_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        ids_resp = await client.get(
            f"{base}/detects/queries/detects/v1",
            params={"limit": min(limit, 100), "sort": "first_behavior|desc"},
            headers=headers,
        )
        if ids_resp.status_code >= 400:
            raise ValueError(f"CrowdStrike query error {ids_resp.status_code}: {ids_resp.text[:300]}")
        ids = (ids_resp.json() or {}).get("resources", [])
        if not ids:
            return []
        detail_resp = await client.post(
            f"{base}/detects/entities/summaries/GET/v1",
            json={"ids": ids},
            headers={**headers, "Content-Type": "application/json"},
        )
    if detail_resp.status_code >= 400:
        raise ValueError(f"CrowdStrike summaries error {detail_resp.status_code}: {detail_resp.text[:300]}")
    resources = (detail_resp.json() or {}).get("resources", [])
    out: list[dict[str, Any]] = []
    for d in resources:
        behaviors = d.get("behaviors") or [{}]
        b0 = behaviors[0] if behaviors else {}
        out.append(
            {
                "vendor": "crowdstrike",
                "external_id": d.get("detection_id", ""),
                "kind": "malware" if b0.get("ioc_type") else "detection",
                "severity": _normalize_severity(d.get("max_severity")),
                "host": (d.get("device") or {}).get("hostname") or "",
                "title": b0.get("display_name") or d.get("detection_id") or "CrowdStrike detection",
                "description": b0.get("description") or "",
                "raw": d,
            }
        )
    return out


def _normalize_stream_event(evt: dict[str, Any]) -> dict[str, Any] | None:
    """Map a raw Falcon Streaming API event envelope to the shared XDR shape.

    Streaming events wrap the interesting bits under ``event`` with a
    top-level ``metadata.eventType`` (e.g. ``DetectionSummaryEvent``,
    ``EppDetectionSummaryEvent``). Anything we don't recognize is skipped
    rather than guessed at.
    """
    meta = evt.get("metadata") or {}
    body = evt.get("event") or {}
    event_type = str(meta.get("eventType") or "").strip()
    if not event_type or "Detection" not in event_type:
        return None  # heartbeats / audit events / unrelated feed noise
    external_id = str(
        body.get("DetectId") or body.get("DetectionId") or meta.get("eventCreationTime") or ""
    ).strip()
    if not external_id:
        return None
    severity_name = str(body.get("SeverityName") or "").lower()
    if not severity_name:
        severity_name = _normalize_severity(body.get("Severity"))
    return {
        "vendor": "crowdstrike",
        "external_id": external_id,
        "kind": "malware" if body.get("IocType") else "detection",
        "severity": severity_name if severity_name in ("critical", "high", "medium", "low") else "medium",
        "host": body.get("Hostname") or body.get("ComputerName") or "",
        "title": body.get("DetectDescription") or body.get("Tactic") or event_type,
        "description": body.get("DetectDescription") or "",
        "raw": evt,
    }


async def _discover_stream(client: httpx.AsyncClient, token: str) -> dict[str, Any]:
    base = settings.crowdstrike_base_url.rstrip("/")
    resp = await client.get(
        f"{base}/sensors/entities/datafeed/v2",
        params={"appId": "securaiq"},
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code >= 400:
        raise ValueError(f"CrowdStrike stream discover error {resp.status_code}: {resp.text[:300]}")
    resources = (resp.json() or {}).get("resources") or []
    if not resources:
        raise ValueError("CrowdStrike stream discover returned no feed resources")
    return resources[0]


async def stream_events() -> AsyncIterator[dict[str, Any]]:
    """Hold open the Falcon Streaming API and yield normalized detections as
    they arrive — genuine push, not a poll loop. Reconnects on any failure;
    the caller (app/xdr_stream.py) wraps this in its own outer retry/backoff
    so a single dropped connection doesn't kill the background task.

    Requires the API client to also have the "Event streams: Read" scope —
    a client with only "Detections: Read" will get a 403 on discover, in
    which case the caller should fall back to the existing poll-based
    `fetch_detections()` / `xdr_sync` job.
    """
    if not is_configured():
        return
    async with httpx.AsyncClient(timeout=None) as client:
        token = await _access_token(client)
        feed = await _discover_stream(client, token)
        feed_url = feed.get("dataFeedURL")
        session_token = ((feed.get("sessionToken") or {}).get("token")) or ""
        refresh_url = feed.get("refreshActiveSessionURL")
        refresh_interval = int(feed.get("refreshActiveSessionInterval") or 1800)
        if not feed_url or not session_token:
            raise ValueError("CrowdStrike stream discover missing dataFeedURL/sessionToken")

        last_refresh = time.time()
        async with client.stream(
            "GET",
            feed_url,
            headers={"Authorization": f"Token {session_token}"},
            timeout=httpx.Timeout(connect=20.0, read=None, write=20.0, pool=20.0),
        ) as resp:
            if resp.status_code >= 400:
                raise ValueError(f"CrowdStrike stream connect error {resp.status_code}")
            async for line in resp.aiter_lines():
                if not line or not line.strip():
                    # Falcon sends periodic blank keep-alive lines on this feed.
                    if refresh_url and time.time() - last_refresh > max(60, refresh_interval - 120):
                        try:
                            await client.post(refresh_url, headers={"Authorization": f"Bearer {token}"})
                            last_refresh = time.time()
                        except Exception:
                            pass  # a missed refresh just means we reconnect sooner via the outer retry loop
                    continue
                try:
                    evt = json.loads(line)
                except Exception:
                    continue
                item = _normalize_stream_event(evt)
                if item is not None:
                    yield item
