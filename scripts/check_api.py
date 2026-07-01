"""Verify all PentestGPT APIs load real data."""

from __future__ import annotations

import json
import sys
import time

import httpx

BASE = "http://localhost:8080"


def main() -> int:
    client = httpx.Client(timeout=180.0)
    failed = False

    def section(name: str, data: object) -> None:
        print(f"\n=== {name} ===")
        if isinstance(data, dict):
            print(json.dumps(data, indent=2))
        else:
            print(str(data)[:800])

    health = client.get(f"{BASE}/api/health").json()
    section("GET /api/health", health)
    if not health.get("backend_ready"):
        print("FAIL: model backend not ready")
        failed = True

    status = client.get(f"{BASE}/api/status").json()
    sources = status.get("rag_sources", [])
    section(
        "GET /api/status",
        {
            "rag_documents": status.get("rag_documents"),
            "sample_sources": sources[:5],
            "more_sources": max(0, len(sources) - 5),
        },
    )
    if not status.get("rag_documents"):
        print("FAIL: no RAG documents loaded")
        failed = True

    models = client.get(f"{BASE}/api/models").json()
    section("GET /api/models", models)

    modes = client.get(f"{BASE}/api/modes").json()
    section(
        "GET /api/modes",
        {
            "modes": modes.get("modes"),
            "quick_prompts_default": modes.get("quick_prompts", {}).get("default"),
        },
    )

    started = time.time()
    with client.stream(
        "POST",
        f"{BASE}/api/chat",
        json={
            "message": "What is OWASP A01? Answer in 2 sentences.",
            "history": [],
            "mode": "default",
            "use_rag": True,
        },
    ) as response:
        response.raise_for_status()
        rag_chat = "".join(response.iter_text())
    section(
        "POST /api/chat (RAG on)",
        {"time_s": round(time.time() - started, 1), "response": rag_chat[:600]},
    )
    if not rag_chat.strip():
        print("FAIL: empty RAG chat response")
        failed = True

    started = time.time()
    with client.stream(
        "POST",
        f"{BASE}/api/chat",
        json={
            "message": "Reply with exactly: API test ok",
            "history": [],
            "mode": "default",
            "use_rag": False,
        },
    ) as response:
        response.raise_for_status()
        plain_chat = "".join(response.iter_text())
    section(
        "POST /api/chat (RAG off)",
        {"time_s": round(time.time() - started, 1), "response": plain_chat[:300]},
    )
    if not plain_chat.strip():
        print("FAIL: empty plain chat response")
        failed = True

    print(f"\n=== RESULT: {'PASS' if not failed else 'FAIL'} ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
