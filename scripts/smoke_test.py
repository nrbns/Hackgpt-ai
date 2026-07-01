"""Smoke test for PentestGPT API."""

from __future__ import annotations

import argparse
import sys

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="PentestGPT smoke test")
    parser.add_argument(
        "--chat",
        action="store_true",
        help="Send a short chat message (slow on HuggingFace CPU)",
    )
    parser.add_argument("--base", default="http://localhost:8080", help="Server base URL")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    with httpx.Client(timeout=30.0) as client:
        health = client.get(f"{base}/api/health").json()
        backend = client.get(f"{base}/api/backend").json()
        status = client.get(f"{base}/api/status").json()

    print("health:", health)
    print("backend:", backend)
    print("rag_documents:", status.get("rag_documents"))

    if health.get("status") != "ok":
        return 1
    if not health.get("backend"):
        return 1

    if args.chat:
        timeout = 600.0 if health.get("backend") == "huggingface" else 120.0
        print(f"\nchat test (timeout={timeout}s)...")
        with httpx.Client(timeout=timeout) as client:
            with client.stream(
                "POST",
                f"{base}/api/chat",
                json={
                    "message": "Reply with exactly: smoke test ok",
                    "history": [],
                    "mode": "default",
                    "use_rag": False,
                },
            ) as response:
                response.raise_for_status()
                text = "".join(response.iter_text())
        print("chat response:", text[:500])
        if not text.strip():
            print("empty chat response")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
