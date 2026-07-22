"""GET/POST helpers for runtime settings (API keys, model paths)."""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.env_persist import update_env_value
from app.platform_info import normalize_path
from app.secrets import is_blank_or_placeholder, is_secret_field, mask_secret


def public_settings() -> dict[str, Any]:
    """Safe settings for the UI — secrets never returned in cleartext."""
    payload = {
        "model_backend": settings.model_backend,
        "ollama_base_url": settings.ollama_base_url,
        "ollama_model": settings.ollama_model,
        "openai_compat_base_url": settings.openai_compat_base_url,
        "openai_compat_model": settings.openai_compat_model,
        "openai_compat_api_key_set": bool(settings.openai_compat_api_key),
        "openai_compat_api_key_masked": mask_secret(settings.openai_compat_api_key),
        "hermes_base_url": settings.hermes_base_url,
        "hermes_model": settings.hermes_model,
        "hermes_api_key_set": bool(settings.hermes_api_key),
        "hermes_api_key_masked": mask_secret(settings.hermes_api_key),
        "hermes_session_key_set": bool(settings.hermes_session_key),
        "hermes_session_key_masked": mask_secret(settings.hermes_session_key),
        "hermes_show_tool_progress": settings.hermes_show_tool_progress,
        "hf_model": settings.hf_model,
        "hf_token_set": bool(settings.hf_token),
        "hf_token_masked": mask_secret(settings.hf_token),
        "unsloth_model": settings.unsloth_model,
        "unsloth_adapter_dir": settings.unsloth_adapter_dir,
        "unsloth_max_seq_length": settings.unsloth_max_seq_length,
        "unsloth_load_in_4bit": settings.unsloth_load_in_4bit,
        "web_search_enabled": settings.web_search_enabled,
    }
    # Defense-in-depth: never allow raw secret keys in the payload
    forbidden = {
        "hf_token",
        "openai_compat_api_key",
        "hermes_api_key",
        "hermes_session_key",
        "api_key",
        "token",
        "password",
    }
    for key in list(payload):
        if key.lower() in forbidden or (
            is_secret_field(key) and not key.endswith("_set") and not key.endswith("_masked")
        ):
            payload.pop(key, None)
    return payload


# Keys that may be written from the Settings UI (never echo secrets back).
_WRITABLE: dict[str, tuple[str, type]] = {
    "openai_compat_base_url": ("OPENAI_COMPAT_BASE_URL", str),
    "openai_compat_model": ("OPENAI_COMPAT_MODEL", str),
    "openai_compat_api_key": ("OPENAI_COMPAT_API_KEY", str),
    "hermes_base_url": ("HERMES_BASE_URL", str),
    "hermes_model": ("HERMES_MODEL", str),
    "hermes_api_key": ("HERMES_API_KEY", str),
    "hermes_session_key": ("HERMES_SESSION_KEY", str),
    "hermes_show_tool_progress": ("HERMES_SHOW_TOOL_PROGRESS", bool),
    "hf_model": ("HF_MODEL", str),
    "hf_token": ("HF_TOKEN", str),
    "unsloth_model": ("UNSLOTH_MODEL", str),
    "unsloth_adapter_dir": ("UNSLOTH_ADAPTER_DIR", str),
    "unsloth_max_seq_length": ("UNSLOTH_MAX_SEQ_LENGTH", int),
    "unsloth_load_in_4bit": ("UNSLOTH_LOAD_IN_4BIT", bool),
    "ollama_base_url": ("OLLAMA_BASE_URL", str),
    "ollama_model": ("OLLAMA_MODEL", str),
}


def apply_settings_patch(data: dict[str, Any]) -> dict[str, Any]:
    updated: list[str] = []
    for field, (env_key, typ) in _WRITABLE.items():
        if field not in data:
            continue
        raw = data[field]
        if raw is None:
            continue

        # Skip blank / placeholder secrets (UI empty = keep existing)
        if is_secret_field(field):
            if is_blank_or_placeholder(raw):
                continue

        if typ is bool:
            value = bool(raw) if not isinstance(raw, str) else raw.strip().lower() in {"1", "true", "yes", "on"}
            setattr(settings, field, value)
            update_env_value(env_key, "true" if value else "false")
        elif typ is int:
            value = int(raw)
            setattr(settings, field, value)
            update_env_value(env_key, str(value))
        else:
            value = str(raw).strip()
            if field.endswith("_dir") or field.endswith("_path"):
                value = normalize_path(value) if value else value
            setattr(settings, field, value)
            update_env_value(env_key, value)
            # Keep process env in sync for HF hub clients
            if field == "hf_token":
                import os

                os.environ["HF_TOKEN"] = value
                os.environ["HUGGING_FACE_HUB_TOKEN"] = value
        updated.append(field)

    # Response only includes masked public settings — never raw secrets
    return {"updated": updated, "settings": public_settings()}
