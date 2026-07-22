"""Nous Hermes Agent API client (OpenAI-compatible gateway api_server).

https://github.com/NousResearch/hermes-agent
https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import settings


def _auth_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {settings.hermes_api_key}",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


def _root_base() -> str:
    """http://127.0.0.1:8642 from .../v1"""
    base = settings.hermes_base_url.rstrip("/")
    if base.endswith("/v1"):
        return base[:-3]
    return base


def _v1_base() -> str:
    base = settings.hermes_base_url.rstrip("/")
    return base if base.endswith("/v1") else f"{base}/v1"


async def hermes_reachable() -> bool:
    headers = _auth_headers()
    candidates = [
        f"{_v1_base()}/models",
        f"{_v1_base()}/health",
        f"{_root_base()}/health",
    ]
    timeout = httpx.Timeout(connect=1.5, read=2.0, write=2.0, pool=2.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            for url in candidates:
                try:
                    if (await client.get(url, headers=headers)).status_code == 200:
                        return True
                except httpx.HTTPError:
                    continue
    except httpx.HTTPError:
        return False
    return False


async def fetch_hermes_status() -> dict[str, Any]:
    """Aggregate health, models, and capabilities for the UI."""
    headers = _auth_headers()
    out: dict[str, Any] = {
        "reachable": False,
        "base_url": settings.hermes_base_url,
        "model": settings.hermes_model,
        "session_key_set": bool(settings.hermes_session_key),
        "health": None,
        "models": [],
        "capabilities": None,
        "error": None,
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            for url in (f"{_root_base()}/health", f"{_v1_base()}/health"):
                try:
                    r = await client.get(url, headers=headers)
                    if r.status_code == 200:
                        out["reachable"] = True
                        try:
                            out["health"] = r.json()
                        except Exception:
                            out["health"] = {"status": "ok"}
                        break
                except httpx.HTTPError:
                    continue

            if not out["reachable"]:
                out["error"] = (
                    "Hermes API not reachable — run `hermes gateway` with API_SERVER_ENABLED=true"
                )
                return out

            try:
                r = await client.get(f"{_v1_base()}/models", headers=headers)
                if r.status_code == 200:
                    data = r.json()
                    out["models"] = [
                        m.get("id")
                        for m in data.get("data", [])
                        if isinstance(m, dict) and m.get("id")
                    ]
            except httpx.HTTPError:
                pass

            try:
                r = await client.get(f"{_v1_base()}/capabilities", headers=headers)
                if r.status_code == 200:
                    out["capabilities"] = r.json()
            except httpx.HTTPError:
                pass

            try:
                r = await client.get(f"{_root_base()}/health/detailed", headers=headers)
                if r.status_code == 200:
                    out["health_detailed"] = r.json()
            except httpx.HTTPError:
                pass
    except Exception as exc:
        out["error"] = str(exc)
    return out


def _format_tool_progress(data: dict[str, Any]) -> str | None:
    tool = data.get("tool") or data.get("name") or data.get("tool_name")
    status = data.get("status") or data.get("phase") or data.get("event")
    detail = data.get("detail") or data.get("message") or data.get("preview") or ""
    if not tool and not detail:
        nested = data.get("data") if isinstance(data.get("data"), dict) else {}
        tool = nested.get("tool") or nested.get("name")
        status = nested.get("status") or status
        detail = nested.get("detail") or nested.get("message") or ""
    if not tool and not detail:
        return None
    label = tool or "tool"
    bit = f" ({status})" if status else ""
    extra = f" — {detail}" if detail else ""
    return f"\n\n_Hermes tool `{label}`{bit}{extra}_\n\n"


async def stream_hermes_chat(
    messages: list[dict[str, str]],
    *,
    session_id: str | None = None,
    session_key: str | None = None,
) -> AsyncIterator[tuple[str, str | None]]:
    """
    Stream Hermes chat completions.

    Yields (text_chunk, session_id_or_none). session_id is emitted once when
    known from response headers.
    """
    url = f"{_v1_base()}/chat/completions"
    payload = {
        "model": settings.hermes_model,
        "messages": messages,
        "stream": True,
        "temperature": 0.7,
    }
    extra: dict[str, str] = {}
    if session_id:
        extra["X-Hermes-Session-Id"] = session_id[:256]
    key = (session_key if session_key is not None else settings.hermes_session_key) or ""
    if key.strip():
        extra["X-Hermes-Session-Key"] = key.strip()[:256]
    headers = _auth_headers(extra)

    try:
        timeout = httpx.Timeout(connect=10.0, read=600.0, write=30.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                echoed = response.headers.get("x-hermes-session-id") or response.headers.get(
                    "X-Hermes-Session-Id"
                )
                if echoed:
                    yield ("", echoed)

                if response.status_code != 200:
                    body = await response.aread()
                    yield (
                        (
                            f"**Hermes Agent error** ({response.status_code}): {body.decode()}\n\n"
                            "Install/configure Hermes Agent, then:\n"
                            "1. `hermes setup` or `hermes setup --portal`\n"
                            "2. Set `API_SERVER_ENABLED=true` and `API_SERVER_KEY` "
                            "(must match HackGPT `HERMES_API_KEY`)\n"
                            "3. `hermes gateway` → "
                            f"`{settings.hermes_base_url}`\n\n"
                            "Scripts: `.\\scripts\\use_hermes.ps1` / `bash scripts/use_hermes.sh`\n"
                            "Repo: https://github.com/NousResearch/hermes-agent"
                        ),
                        None,
                    )
                    return

                event_name = "message"
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    if line.startswith("event:"):
                        event_name = line[6:].strip() or "message"
                        continue
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    if event_name == "hermes.tool.progress" or data.get("object") == "hermes.tool.progress":
                        tip = _format_tool_progress(data)
                        if tip:
                            yield (tip, None)
                        event_name = "message"
                        continue

                    if (
                        data.get("type") == "hermes.tool.progress"
                        or ("tool" in data and "choices" not in data)
                    ):
                        tip = _format_tool_progress(data)
                        if tip:
                            yield (tip, None)
                        continue

                    choices = data.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {}) or {}
                    content = delta.get("content") or ""
                    if content:
                        yield (content, None)
                    event_name = "message"
    except httpx.ConnectError:
        yield (
            (
                "**Cannot connect to Hermes Agent API server.**\n\n"
                "1. Install: `iex (irm https://hermes-agent.nousresearch.com/install.ps1)` (Windows)\n"
                "   or `curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash`\n"
                "2. `hermes setup` (+ `API_SERVER_ENABLED=true` / matching `API_SERVER_KEY`)\n"
                "3. `hermes gateway`\n"
                f"4. URL `{settings.hermes_base_url}` and key must match HackGPT Settings\n\n"
                "https://github.com/NousResearch/hermes-agent"
            ),
            None,
        )
