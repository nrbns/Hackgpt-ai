"""Internal SecuraIQ Admin Health — component status for operators."""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.db import current_backend, get_conn, using_postgres


def _status(ok: bool, detail: str = "", degraded: bool = False) -> dict[str, Any]:
    if ok and not degraded:
        state = "green"
    elif ok and degraded:
        state = "yellow"
    else:
        state = "red"
    return {"status": state, "ok": ok, "detail": detail}


def collect_admin_health() -> dict[str, Any]:
    components: dict[str, dict[str, Any]] = {}

    # API process itself
    components["api"] = _status(True, "process up")

    # Database
    try:
        c = get_conn()
        c.execute("SELECT 1").fetchone()
        backend = current_backend()
        prod = (settings.deployment_mode or "").lower() in {"production", "prod", "commercial", "saas", "cloud"}
        if prod and backend != "postgres":
            components["database"] = _status(False, f"production requires postgres; got {backend}")
        else:
            components["database"] = _status(True, f"backend={backend}")
    except Exception as exc:
        components["database"] = _status(False, str(exc)[:200])

    # Redis (optional)
    redis_url = (settings.redis_url or "").strip()
    if not redis_url:
        components["redis"] = _status(True, "not configured (in-process bus)", degraded=True)
    else:
        try:
            import redis  # type: ignore

            r = redis.from_url(redis_url, socket_connect_timeout=1.5)
            r.ping()
            components["redis"] = _status(True, "ping ok")
        except Exception as exc:
            components["redis"] = _status(False, str(exc)[:200])

    # AI gateway (config readiness — not a live model call)
    backend = settings.model_backend
    if backend == "ollama":
        components["ai_gateway"] = _status(True, f"backend={backend}", degraded=False)
    elif backend in {"openai", "openrouter", "groq", "together", "fireworks"}:
        key_map = {
            "openai": settings.openai_api_key,
            "openrouter": settings.openrouter_api_key,
            "groq": settings.groq_api_key,
            "together": settings.together_api_key,
            "fireworks": settings.fireworks_api_key,
        }
        ok = bool(key_map.get(backend))
        components["ai_gateway"] = _status(ok, f"backend={backend}", degraded=not ok)
    else:
        components["ai_gateway"] = _status(True, f"backend={backend}", degraded=True)

    # Workers — Prefect optional
    if settings.prefect_enabled:
        components["workers"] = _status(True, "prefect enabled", degraded=True)
    else:
        components["workers"] = _status(True, "local asyncio jobs", degraded=True)

    # Integrations — configured count only
    configured = 0
    for flag in (
        settings.wazuh_base_url,
        settings.jira_base_url,
        settings.slack_webhook_url,
        settings.crowdstrike_client_id,
        settings.defender_client_id,
        settings.sentinelone_api_token,
        settings.sophos_client_id,
        settings.sonarqube_base_url,
    ):
        if (flag or "").strip():
            configured += 1
    components["integrations"] = _status(
        True,
        f"{configured} connector(s) configured",
        degraded=configured == 0,
    )

    # Billing
    if settings.stripe_secret_key and settings.stripe_webhook_secret:
        components["billing"] = _status(True, "stripe keys set")
    elif settings.billing_enforcement_enabled:
        components["billing"] = _status(False, "enforcement on but Stripe keys missing")
    else:
        components["billing"] = _status(True, "soft / not enforced", degraded=True)

    overall = "green"
    if any(c["status"] == "red" for c in components.values()):
        overall = "red"
    elif any(c["status"] == "yellow" for c in components.values()):
        overall = "yellow"

    return {
        "overall": overall,
        "deployment_mode": settings.deployment_mode,
        "postgres_required": bool(getattr(settings, "require_postgres_in_production", True)),
        "using_postgres": using_postgres(),
        "components": components,
    }
