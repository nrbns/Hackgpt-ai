"""Verify the Hugging Face token and both HF paths SecuraIQ can use.

Checks, in order:
  1. Token identity      — https://huggingface.co/api/whoami-v2
  2. Cloud inference     — HF Inference Providers router (OpenAI-compatible)
  3. Local Transformers  — packages present + model metadata reachable

Run: .venv/Scripts/python scripts/check_hf.py
"""

from __future__ import annotations

import importlib.util
import os
import sys

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402

WHOAMI_URL = "https://huggingface.co/api/whoami-v2"
ROUTER_URL = "https://router.huggingface.co/v1"
ROUTER_TEST_MODEL = os.environ.get("HF_ROUTER_MODEL", "meta-llama/Llama-3.1-8B-Instruct")


def mask(token: str) -> str:
    if len(token) <= 10:
        return "***"
    return f"{token[:6]}…{token[-4:]}"


def check_whoami(token: str) -> bool:
    print("\n=== 1. Token identity ===")
    try:
        res = httpx.get(WHOAMI_URL, headers={"Authorization": f"Bearer {token}"}, timeout=20.0)
    except Exception as exc:
        print(f"FAIL: cannot reach Hugging Face ({exc})")
        return False
    if res.status_code == 401:
        print("FAIL: token rejected (401) — revoked or mistyped")
        return False
    if res.status_code != 200:
        print(f"FAIL: HTTP {res.status_code} — {res.text[:200]}")
        return False
    data = res.json()
    auth = data.get("auth") or {}
    access = (auth.get("accessToken") or {}).get("role") or auth.get("type") or "unknown"
    print(f"OK: user={data.get('name')} type={data.get('type')} token_role={access}")
    orgs = [o.get("name") for o in data.get("orgs") or []]
    if orgs:
        print(f"    orgs: {', '.join(filter(None, orgs))}")
    if access in {"read", "fineGrained", "unknown"}:
        print("    note: 'write'/inference permission is needed for hosted inference")
    return True


def check_router(token: str) -> bool:
    print("\n=== 2. Cloud inference (HF Inference Providers) ===")
    try:
        res = httpx.post(
            f"{ROUTER_URL}/chat/completions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "model": ROUTER_TEST_MODEL,
                "messages": [{"role": "user", "content": "Reply with the single word: ready"}],
                "max_tokens": 16,
            },
            timeout=60.0,
        )
    except Exception as exc:
        print(f"FAIL: request error ({exc})")
        return False
    if res.status_code != 200:
        print(f"FAIL: HTTP {res.status_code} — {res.text[:300]}")
        print(f"    model tried: {ROUTER_TEST_MODEL} (override with HF_ROUTER_MODEL)")
        return False
    try:
        reply = res.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        print(f"FAIL: unexpected payload — {res.text[:200]}")
        return False
    print(f"OK: model={ROUTER_TEST_MODEL} reply={reply[:60]!r}")
    print(f"    usable as: MODEL_BACKEND=openai_compat, base={ROUTER_URL}")
    return True


def check_local(token: str) -> bool:
    print("\n=== 3. Local Transformers backend ===")
    missing = [p for p in ("torch", "transformers", "accelerate") if not importlib.util.find_spec(p)]
    if missing:
        print(f"WARN: missing packages: {', '.join(missing)}")
        print("      pip install " + " ".join(missing))
    else:
        print("OK: torch + transformers + accelerate present")

    model_id = settings.hf_model
    try:
        res = httpx.get(
            f"https://huggingface.co/api/models/{model_id}",
            headers={"Authorization": f"Bearer {token}"} if token else {},
            timeout=20.0,
        )
    except Exception as exc:
        print(f"FAIL: cannot reach model metadata ({exc})")
        return False
    if res.status_code == 200:
        gated = res.json().get("gated")
        print(f"OK: {model_id} reachable (gated={gated})")
        return not missing
    if res.status_code in (401, 403):
        print(f"FAIL: {model_id} is gated for this token — accept its license on the model page")
        return False
    print(f"FAIL: HTTP {res.status_code} for {model_id}")
    return False


def main() -> int:
    token = (settings.hf_token or os.environ.get("HF_TOKEN") or "").strip()
    print("SecuraIQ — Hugging Face check")
    print(f"backend={settings.model_backend}  hf_model={settings.hf_model}  token={mask(token) if token else 'MISSING'}")
    if not token:
        print("\nFAIL: HF_TOKEN not set in .env")
        return 1

    ok_id = check_whoami(token)
    ok_router = check_router(token)
    ok_local = check_local(token)

    print("\n=== Summary ===")
    print(f"token valid       : {'yes' if ok_id else 'no'}")
    print(f"cloud inference   : {'yes' if ok_router else 'no'}")
    print(f"local transformers: {'yes' if ok_local else 'no'}")
    return 0 if (ok_id and (ok_router or ok_local)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
