"""Full integration check for PentestGPT UI + backend wiring."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
REQUIRED_STATIC = [
    "index.html",
    "app.js",
    "style.css",
    "manifest.webmanifest",
    "icon.svg",
]
REQUIRED_HTML_IDS = [
    "backend",
    "mode",
    "model",
    "useRag",
    "status",
    "settingsBtn",
    "menuToggle",
    "controls",
    "chat",
    "input",
    "send",
    "settingsModal",
    "settingsForm",
    "setOllamaUrl",
    "setOllamaModel",
    "setHfToken",
    "setHfModel",
    "setUnslothModel",
    "setUnslothAdapter",
    "setHermesUrl",
    "setCompatUrl",
    "lanTip",
    "trainUnsloth",
    "preloadModel",
]
BACKENDS = ["ollama", "openai_compat", "hermes", "unsloth", "huggingface"]


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def main() -> int:
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080").rstrip("/")
    errors: list[str] = []

    # --- static files on disk ---
    for name in REQUIRED_STATIC:
        if not (STATIC / name).exists():
            errors.append(f"missing static/{name}")

    html = (STATIC / "index.html").read_text(encoding="utf-8") if (STATIC / "index.html").exists() else ""
    for eid in REQUIRED_HTML_IDS:
        if f'id="{eid}"' not in html:
            errors.append(f"index.html missing id={eid}")

    js = (STATIC / "app.js").read_text(encoding="utf-8") if (STATIC / "app.js").exists() else ""
    for path in (
        "/api/health",
        "/api/backend",
        "/api/settings",
        "/api/platform",
        "/api/finetune",
        "/api/chat",
        "/api/modes",
        "/api/models",
        "/api/ingest",
    ):
        if path not in js:
            errors.append(f"app.js missing fetch to {path}")

    for b in BACKENDS:
        if f'value="{b}"' not in html:
            errors.append(f"index.html missing backend option {b}")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1

    print("OK static + UI ids")

    with httpx.Client(timeout=60.0) as client:
        # static over HTTP
        for name in ("/", "/app.js", "/style.css", "/manifest.webmanifest", "/icon.svg"):
            r = client.get(f"{base}{name}")
            if r.status_code != 200:
                fail(f"GET {name} -> {r.status_code}")
        print("OK static HTTP")

        health = client.get(f"{base}/api/health").json()
        if health.get("status") != "ok":
            fail(f"health={health}")
        print("OK /api/health", health.get("backend"), "rag=", health.get("rag_documents"))

        backend = client.get(f"{base}/api/backend").json()
        for b in BACKENDS:
            if b not in backend.get("options", []):
                fail(f"backend options missing {b}: {backend}")
        print("OK /api/backend options")

        modes = client.get(f"{base}/api/modes").json()
        if not modes.get("modes") or not modes.get("quick_prompts"):
            fail(f"modes incomplete: {modes}")
        print("OK /api/modes", modes["modes"])

        models = client.get(f"{base}/api/models").json()
        if "current" not in models:
            fail(f"models: {models}")
        print("OK /api/models")

        settings = client.get(f"{base}/api/settings").json()
        for key in (
            "ollama_base_url",
            "hermes_base_url",
            "hf_token_set",
            "unsloth_model",
            "openai_compat_base_url",
        ):
            if key not in settings:
                fail(f"settings missing {key}")
        print("OK /api/settings")

        platform = client.get(f"{base}/api/platform").json()
        if not platform.get("os") or "backends" not in platform:
            fail(f"platform: {platform}")
        print("OK /api/platform", platform.get("os"), platform.get("lan_urls"))

        probe = client.get(f"{base}/api/backends/probe").json()
        if "recommended" not in probe or "backends" not in probe:
            fail(f"probe: {probe}")
        print("OK /api/backends/probe recommended=", probe.get("recommended"))

        hermes = client.get(f"{base}/api/hermes/status").json()
        if "reachable" not in hermes:
            fail(f"hermes status: {hermes}")
        print("OK /api/hermes/status reachable=", hermes.get("reachable"))

        ft = client.get(f"{base}/api/finetune").json()
        if ft.get("status") not in ("idle", "running", "completed", "failed"):
            fail(f"finetune: {ft}")
        print("OK /api/finetune", ft.get("status"))

        # settings round-trip (non-destructive)
        patch = client.post(
            f"{base}/api/settings",
            json={"unsloth_max_seq_length": settings.get("unsloth_max_seq_length") or 2048},
        )
        if patch.status_code != 200:
            fail(f"settings POST {patch.status_code} {patch.text}")
        print("OK POST /api/settings")

        # backend switch round-trip through all options, restore original
        original = backend.get("backend") or "ollama"
        for b in BACKENDS:
            r = client.post(f"{base}/api/backend", json={"backend": b})
            if r.status_code != 200:
                fail(f"switch {b}: {r.status_code} {r.text}")
            cur = client.get(f"{base}/api/backend").json().get("backend")
            if cur != b:
                fail(f"switch stuck: wanted {b} got {cur}")
            h = client.get(f"{base}/api/health").json()
            if h.get("backend") != b:
                fail(f"health backend mismatch after switch to {b}")
        client.post(f"{base}/api/backend", json={"backend": original})
        print("OK backend switch all:", ", ".join(BACKENDS), f"(restored {original})")

        # ingest
        ing = client.post(f"{base}/api/ingest")
        if ing.status_code != 200:
            fail(f"ingest {ing.status_code}")
        print("OK POST /api/ingest", ing.json())

        # chat guardrail + streaming path (may refuse or answer; must stream something)
        with client.stream(
            "POST",
            f"{base}/api/chat",
            json={
                "message": "Reply with exactly: integration ok",
                "history": [],
                "mode": "default",
                "use_rag": False,
            },
        ) as resp:
            if resp.status_code != 200:
                fail(f"chat status {resp.status_code}")
            text = "".join(resp.iter_text())
        if not text.strip():
            # offline backend often returns a help message — empty is still a fail
            fail("chat returned empty body")
        print("OK POST /api/chat (stream len=", len(text), ")")
        print("chat preview:", text[:180].replace("\n", " "))

        status = client.get(f"{base}/api/status").json()
        if status.get("rag_documents", 0) < 1:
            fail(f"expected RAG docs: {status}")
        print("OK /api/status rag=", status.get("rag_documents"))

    print("\nALL INTEGRATION CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
