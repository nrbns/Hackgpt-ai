"""SecuraIQ AI Router — intent lanes + multi-provider model selection.

Enterprise posture: combine general LLMs with frameworks, scanners, and intel feeds.
No "uncensored crimeware" foundation — prefer evidence-grounded, predictable answers.
"""

from __future__ import annotations

import re
from typing import Any

from app.config import settings

# OpenAI-compatible cloud providers (same /chat/completions shape)
CLOUD_PROVIDERS: dict[str, dict[str, Any]] = {
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "env_key": "openai_api_key",
        "best_for": "General reasoning, report writing",
    },
    "openrouter": {
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-4o-mini",
        "env_key": "openrouter_api_key",
        "best_for": "Many models via one API (Claude, Gemini, Qwen, …)",
    },
    "groq": {
        "label": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "env_key": "groq_api_key",
        "best_for": "Fast inference for open models",
    },
    "together": {
        "label": "Together AI",
        "base_url": "https://api.together.xyz/v1",
        "default_model": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        "env_key": "together_api_key",
        "best_for": "Hosted open-source models",
    },
    "fireworks": {
        "label": "Fireworks AI",
        "base_url": "https://api.fireworks.ai/inference/v1",
        "default_model": "accounts/fireworks/models/llama-v3p1-70b-instruct",
        "env_key": "fireworks_api_key",
        "best_for": "Fast open-source model inference",
    },
}

LOCAL_PROVIDERS = ("ollama", "openai_compat", "hermes", "huggingface", "unsloth")

_CODE = re.compile(
    r"\b(code\s*review|script|exploit|payload|python|bash|powershell|regex|semgrep|sast|"
    r"review\s+this\s+(file|code)|sql\s*injection|xss|secure\s*coding)\b",
    re.I,
)
_COMPLIANCE = re.compile(
    r"\b(iso\s*27001|nist|cis\s*control|soc\s*2|pci|asvs|gap\s*analysis|"
    r"control|evidence|audit|policy|compliance|framework)\b",
    re.I,
)
_INTEL = re.compile(
    r"\b(cve-\d{4}|kev|nvd|mitre|att&ck|threat\s*intel|ioc|malware\s*family|"
    r"campaign|advisory|exploit\s*kit)\b",
    re.I,
)
_REPORT = re.compile(
    r"\b(report|executive|board|ciso|roadmap|kpi|posture\s*summary|"
    r"board[- ]ready|status\s*update)\b",
    re.I,
)
_SCAN = re.compile(
    r"\b(scan|nmap|trivy|gitleaks|nuclei|zap|burp|openvas|greenbone|assess|"
    r"ports?|vulnerability\s*import)\b",
    re.I,
)
_CLOUD = re.compile(r"\b(aws|azure|gcp|iam|s3|cloud\s*trail|defender)\b", re.I)


def classify_intent(message: str, mode: str = "default") -> str:
    """Return lane: code | compliance | threat_intel | report | scan | cloud | general."""
    msg = message or ""
    mode = (mode or "default").lower()

    # Explicit modes pin a lane
    mode_lane = {
        "appsec": "code",
        "lab_offensive": "code",
        "ctf": "code",
        "lab": "code",
        "purple": "code",
        "ciso": "compliance",
        "tabletop": "compliance",
        "research": "threat_intel",
        "threat_hunt": "threat_intel",
        "malware": "threat_intel",
        "cloud": "cloud",
        "assess": "scan",
        "awareness": "general",
    }
    if mode in mode_lane:
        return mode_lane[mode]
    if mode == "ir" and _REPORT.search(msg):
        return "report"

    if _CODE.search(msg):
        return "code"
    if _COMPLIANCE.search(msg):
        return "compliance"
    if _INTEL.search(msg):
        return "threat_intel"
    if _CLOUD.search(msg):
        return "cloud"
    if _SCAN.search(msg):
        return "scan"
    if _REPORT.search(msg):
        return "report"
    return "general"


def agent_for_intent(intent: str) -> str:
    return {
        "code": "Secure Code Reviewer",
        "compliance": "Compliance Officer",
        "threat_intel": "Threat Hunter",
        "report": "Executive Report Writer",
        "scan": "SOC Analyst",
        "cloud": "Cloud Security Advisor",
        "general": "Security Advisor",
    }.get(intent, "Security Advisor")


def cloud_key_configured(provider: str) -> bool:
    meta = CLOUD_PROVIDERS.get(provider)
    if not meta:
        return False
    return bool(getattr(settings, meta["env_key"], "") or "")


# Back-compat alias
_cloud_key_configured = cloud_key_configured


def preferred_backend_for_intent(intent: str) -> tuple[str, str]:
    """Pick (backend, model) — prefer configured cloud, else current local."""
    current = settings.model_backend

    # Lane → preferred cloud provider if key present
    lane_cloud = {
        "code": ("openrouter", getattr(settings, "router_code_model", "") or "qwen/qwen2.5-coder-32b-instruct"),
        "compliance": ("openai", getattr(settings, "router_compliance_model", "") or "gpt-4o-mini"),
        "report": ("openai", getattr(settings, "router_report_model", "") or "gpt-4o-mini"),
        "threat_intel": ("groq", getattr(settings, "router_intel_model", "") or "llama-3.3-70b-versatile"),
        "cloud": ("openrouter", getattr(settings, "router_cloud_model", "") or "openai/gpt-4o-mini"),
        "scan": (current, ""),  # tool-heavy — keep current
        "general": (current, ""),
    }
    provider, model = lane_cloud.get(intent, (current, ""))

    if provider in CLOUD_PROVIDERS and _cloud_key_configured(provider):
        if not model:
            model = CLOUD_PROVIDERS[provider]["default_model"]
        return provider, model

    # Fallback: OpenRouter as multi-model hub if configured
    if _cloud_key_configured("openrouter") and intent in {"code", "compliance", "report", "threat_intel", "cloud"}:
        return "openrouter", model or CLOUD_PROVIDERS["openrouter"]["default_model"]

    # Local preferences
    if intent == "code" and current == "ollama":
        return "ollama", settings.ollama_coder_model or settings.ollama_model
    return current, ""


def route_task(
    message: str,
    mode: str = "default",
    *,
    apply_cloud: bool | None = None,
) -> dict[str, Any]:
    """Plan a route for this question (does not mutate settings unless caller applies)."""
    intent = classify_intent(message, mode)
    agent = agent_for_intent(intent)
    backend, model = preferred_backend_for_intent(intent)
    use_router = settings.router_enabled if apply_cloud is None else apply_cloud

    enrich = {
        "threat_intel": intent == "threat_intel",
        "frameworks": intent in {"compliance", "report"},
        "scanners": intent in {"code", "scan"},
        "graph": intent in {"report", "scan", "threat_intel"},
    }

    reason_map = {
        "code": "Code/security review → coder-capable model + Semgrep/Gitleaks context",
        "compliance": "Controls/evidence → strong instruction model + framework RAG",
        "threat_intel": "CVE/KEV/ATT&CK → intel feeds + reasoning model",
        "report": "Executive writing → high-quality general LLM",
        "scan": "Assessment is tool-heavy; keep current backend, interpret scanner output",
        "cloud": "Cloud posture → IAM/config reasoning model",
        "general": "General security Q&A on current backend",
    }

    return {
        "intent": intent,
        "agent": agent,
        "current_backend": settings.model_backend,
        "recommended_backend": backend if use_router else settings.model_backend,
        "recommended_model": model if use_router else "",
        "reason": reason_map.get(intent, "Keep current backend"),
        "enrich": enrich,
        "mode": mode,
        "router_enabled": settings.router_enabled,
        "apply": use_router and backend != settings.model_backend,
        "providers_configured": {
            p: _cloud_key_configured(p) for p in CLOUD_PROVIDERS
        },
    }


def router_system_hint(plan: dict[str, Any]) -> str:
    """Compact system addendum for the chosen agent lane."""
    enrich = plan.get("enrich") or {}
    bits = [
        f"## AI Router lane: **{plan.get('intent')}**",
        f"Act as **{plan.get('agent')}** for this turn.",
        f"Routing note: {plan.get('reason')}",
    ]
    if enrich.get("threat_intel"):
        bits.append("Prefer CISA KEV / NVD / MITRE facts when present in context; cite CVE IDs.")
    if enrich.get("frameworks"):
        bits.append("Ground answers in ISO/NIST/CIS/SOC2/PCI/ASVS controls and evidence when available.")
    if enrich.get("scanners"):
        bits.append("Interpret scanner findings (Trivy/Semgrep/Gitleaks); do not invent scan results.")
    bits.append("Stay evidence-based; include detection/remediation for offensive technique detail.")
    return "\n".join(bits)


def list_providers() -> dict[str, Any]:
    return {
        "local": [
            {"id": p, "label": p.replace("_", " ").title()}
            for p in LOCAL_PROVIDERS
        ],
        "cloud": [
            {
                "id": pid,
                "label": meta["label"],
                "best_for": meta["best_for"],
                "default_model": meta["default_model"],
                "configured": _cloud_key_configured(pid),
            }
            for pid, meta in CLOUD_PROVIDERS.items()
        ],
        "router_enabled": settings.router_enabled,
        "lanes": ["general", "code", "compliance", "threat_intel", "report", "scan", "cloud"],
        "agents": [agent_for_intent(i) for i in ("code", "compliance", "threat_intel", "report", "scan", "cloud", "general")],
    }


def resolve_openai_compat_endpoint(backend: str | None = None) -> tuple[str, str, str]:
    """Return (base_url, api_key, model) for OpenAI-compatible streaming."""
    b = backend or settings.model_backend
    if b in CLOUD_PROVIDERS:
        meta = CLOUD_PROVIDERS[b]
        key = getattr(settings, meta["env_key"], "") or ""
        model = getattr(settings, f"{b}_model", "") or meta["default_model"]
        return meta["base_url"], key, model
    return (
        settings.openai_compat_base_url,
        settings.openai_compat_api_key,
        settings.openai_compat_model,
    )
