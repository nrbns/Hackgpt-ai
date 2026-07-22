"""Probe which AI backends are actually usable right now."""

from __future__ import annotations

import asyncio
from typing import Any

from app.backends import hermes_reachable, openai_compat_reachable
from app.config import settings
from app.ollama_models import list_installed_models, ollama_reachable


def _transformers_ok() -> bool:
    try:
        import transformers  # noqa: F401
        import torch  # noqa: F401

        return True
    except ImportError:
        return False


def _unsloth_ok() -> bool:
    try:
        import unsloth  # noqa: F401

        return True
    except ImportError:
        return False


async def probe_backends() -> dict[str, Any]:
    ollama_up, openai_up, hermes_up = await asyncio.gather(
        ollama_reachable(),
        openai_compat_reachable(),
        hermes_reachable(),
    )
    installed = await list_installed_models() if ollama_up else []
    ollama_ready = bool(ollama_up and installed)
    hf_ok = _transformers_ok()
    unsloth_ok = _unsloth_ok()

    backends = {
        "ollama": {
            "ready": ollama_ready,
            "reachable": ollama_up,
            "detail": "ready" if ollama_ready else ("needs_model" if ollama_up else "offline"),
            "models": installed[:12],
        },
        "openai_compat": {
            "ready": openai_up,
            "reachable": openai_up,
            "detail": "ready" if openai_up else "offline",
        },
        "hermes": {
            "ready": hermes_up,
            "reachable": hermes_up,
            "detail": "ready" if hermes_up else "offline",
        },
        "unsloth": {
            "ready": unsloth_ok,
            "reachable": unsloth_ok,
            "detail": "loads_on_chat" if unsloth_ok else "not_installed",
        },
        "huggingface": {
            "ready": hf_ok,
            "reachable": hf_ok,
            "detail": "loads_on_chat" if hf_ok else "not_installed",
        },
    }

    # Prefer live remote/local servers, then local-in-process fallbacks
    preference = ["ollama", "hermes", "openai_compat", "huggingface", "unsloth"]
    recommended = None
    for name in preference:
        if backends[name]["ready"]:
            recommended = name
            break

    current = settings.model_backend
    current_ready = bool(backends.get(current, {}).get("ready"))

    return {
        "current": current,
        "current_ready": current_ready,
        "recommended": recommended,
        "backends": backends,
    }
