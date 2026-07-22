from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Literal

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import settings
from app.guardrails import check_request
from app.model_client import model_client
from app.prompts import (
    ASSESS_MODE_PROMPT,
    AWARENESS_MODE_PROMPT,
    BLUETEAM_MODE_PROMPT,
    CISO_MODE_PROMPT,
    CTF_MODE_PROMPT,
    LAB_MODE_PROMPT,
    LAB_OFFENSIVE_MODE_PROMPT,
    MALWARE_ANALYSIS_MODE_PROMPT,
    REDTEAM_MODE_PROMPT,
    RESEARCH_MODE_PROMPT,
    SEARCH_BEHAVIOR_PROMPT,
    SYSTEM_PROMPT,
    TOOLS_BEHAVIOR_PROMPT,
)
from app.backends import hermes_reachable, openai_compat_reachable
from app.env_persist import update_env_value
from app.fine_tune.job import finetune_job, launch_unsloth_job
from app.hermes_client import fetch_hermes_status
from app.net_assess import assess_from_request, extract_targets, format_assess_context
from app.ollama_models import RECOMMENDED_MODELS, fetch_ollama_tags, list_installed_models, pull_model
from app.platform_info import platform_info
from app.probe import probe_backends
from app.rag import rag_engine
from app.settings_api import apply_settings_patch, public_settings
from app.tools import format_tools_context, list_tools_status, run_security_tools
from app.web_search import format_search_context, web_search

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        count = rag_engine.ingest_directory(force=False)
        if count:
            print(f"RAG: indexed {count} knowledge documents.")
        else:
            existing = rag_engine.document_count()
            if existing:
                print(f"RAG: using existing index ({existing} docs) — fast start.")
    except Exception as exc:
        print(f"RAG ingest skipped: {exc}")
    if settings.model_backend == "huggingface":
        print(f"HuggingFace backend: {settings.hf_model} (preloading in background)")

        async def _bg_preload() -> None:
            try:
                await model_client.preload_huggingface()
                print("HuggingFace model ready.")
            except Exception as exc:
                print(f"HuggingFace preload deferred: {exc}")

        asyncio.create_task(_bg_preload())
    elif settings.model_backend == "unsloth":
        print(f"Unsloth backend: {settings.unsloth_model} (loads on first chat)")
    elif settings.model_backend == "hermes":
        print(f"Hermes backend: {settings.hermes_base_url}")
    yield


app = FastAPI(title="HackGPT", version="1.4.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Hermes-Session-Id", "X-Hermes-Session-Key"],
)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=16000)
    history: list[ChatMessage] = Field(default_factory=list)
    mode: Literal[
        "default",
        "ctf",
        "lab",
        "redteam",
        "blueteam",
        "malware",
        "research",
        "lab_offensive",
        "assess",
        "ciso",
        "awareness",
    ] = "default"
    use_rag: bool = True
    use_web_search: bool | None = None
    use_net_assess: bool | None = None
    use_local_tools: bool | None = None
    tools: list[str] | None = None
    target: str | None = Field(default=None, max_length=253)
    authorized_target: bool = False
    hermes_session_id: str | None = Field(default=None, max_length=256)
    reset_hermes_session: bool = False


class IngestResponse(BaseModel):
    documents_ingested: int


class ModelSwitchRequest(BaseModel):
    model: str = Field(min_length=1, max_length=128)


class ModelPullRequest(BaseModel):
    model: str = Field(min_length=1, max_length=128)


class BackendSwitchRequest(BaseModel):
    backend: Literal["ollama", "openai_compat", "hermes", "unsloth", "huggingface"]


class SettingsUpdateRequest(BaseModel):
    openai_compat_base_url: str | None = None
    openai_compat_model: str | None = None
    openai_compat_api_key: str | None = None
    hermes_base_url: str | None = None
    hermes_model: str | None = None
    hermes_api_key: str | None = None
    hermes_session_key: str | None = None
    hermes_show_tool_progress: bool | None = None
    hf_model: str | None = None
    hf_token: str | None = None
    unsloth_model: str | None = None
    unsloth_adapter_dir: str | None = None
    unsloth_max_seq_length: int | None = None
    unsloth_load_in_4bit: bool | None = None
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    web_search_enabled: bool | None = None
    web_search_max_results: int | None = None
    web_search_timeout_sec: float | None = None
    searxng_url: str | None = None
    net_assess_enabled: bool | None = None
    net_assess_use_nmap: bool | None = None
    local_tools_enabled: bool | None = None
    local_tools_auto: bool | None = None
    local_tools_allow_heavy: bool | None = None


class FinetuneStartRequest(BaseModel):
    engine: Literal["unsloth"] = "unsloth"
    model: str | None = None
    output: str | None = None
    epochs: int = Field(default=1, ge=1, le=10)
    batch_size: int = Field(default=2, ge=1, le=16)


MODE_RAG_TOP_K = {
    "default": 3,
    "ctf": 3,
    "lab": 4,
    "redteam": 4,
    "blueteam": 5,
    "malware": 5,
    "research": 4,
    "lab_offensive": 5,
    "assess": 5,
    "ciso": 5,
    "awareness": 5,
}

QUICK_PROMPTS = {
    "default": [
        "Explain OWASP Top 10 with examples",
        "How do I scope a pentest engagement?",
    ],
    "ctf": [
        "Web CTF enumeration checklist",
        "How do I approach a crypto CTF challenge?",
    ],
    "lab": [
        "Set up DVWA in a local VM safely",
        "sqlmap usage against my own lab target",
    ],
    "redteam": [
        "Metasploit workflow for Metasploitable 2",
        "BEEF hook demo in Juice Shop lab",
    ],
    "blueteam": [
        "Sigma rule for suspicious LSASS access",
        "IR steps when ransomware is detected",
    ],
    "malware": [
        "Static analysis workflow for suspicious EXE",
        "Write a YARA rule for PowerShell download cradle",
    ],
    "research": [
        "Latest critical CVEs affecting Windows this month",
        "Compare Nuclei vs custom scripts for lab recon",
        "Kerberoasting technique, detection, and lab setup",
        "Public writeups for Log4Shell exploitation path",
    ],
    "lab_offensive": [
        "Full attack chain on Metasploitable 2 with detection notes",
        "Lab reverse shell + persistence on a disposable VM",
        "Kerberoasting in an authorized AD lab + Sigma detection",
        "XSS to session hijack demo in Juice Shop + fixes",
    ],
    "assess": [
        "Assess my lab host 192.168.56.101 — prioritize findings",
        "Vulnerability assessment for HTB target 10.10.10.x from open ports",
        "Map banners to CVEs and give verify + remediate steps",
    ],
    "ciso": [
        "30/60/90 day security roadmap for a mid-size company",
        "Board briefing: ransomware risk, controls, and metrics",
        "Map our vuln backlog to ISO 27001 and CIS Controls",
        "How should CISO prioritize Greenbone vs Burp vs EDR spend?",
    ],
    "awareness": [
        "Design an authorized phishing simulation with training banners",
        "Teach users 10 phishing red flags with examples",
        "SPF DKIM DMARC checklist + awareness talking points",
        "Tabletop: employee clicked a fake MFA prompt — IR + coaching",
    ],
}


async def _build_messages(req: ChatRequest) -> list[dict[str, str]]:
    messages: list[dict[str, str]] | None = None
    async for kind, payload in _iter_build_messages(req):
        if kind == "messages":
            messages = payload  # type: ignore[assignment]
    assert messages is not None
    return messages


async def _iter_build_messages(req: ChatRequest):
    """Yield ('phase', name) then ('messages', list) for realtime UI progress."""
    system_parts = [SYSTEM_PROMPT]
    if req.mode == "ctf":
        system_parts.append(CTF_MODE_PROMPT)
    elif req.mode == "lab":
        system_parts.append(LAB_MODE_PROMPT)
    elif req.mode == "redteam":
        system_parts.append(REDTEAM_MODE_PROMPT)
    elif req.mode == "blueteam":
        system_parts.append(BLUETEAM_MODE_PROMPT)
    elif req.mode == "malware":
        system_parts.append(MALWARE_ANALYSIS_MODE_PROMPT)
    elif req.mode == "research":
        system_parts.append(RESEARCH_MODE_PROMPT)
    elif req.mode == "lab_offensive":
        system_parts.append(LAB_OFFENSIVE_MODE_PROMPT)
    elif req.mode == "assess":
        system_parts.append(ASSESS_MODE_PROMPT)
    elif req.mode == "ciso":
        system_parts.append(CISO_MODE_PROMPT)
    elif req.mode == "awareness":
        system_parts.append(AWARENESS_MODE_PROMPT)

    search_default_modes = {"research", "assess", "lab_offensive", "ciso", "awareness"}
    do_search = (
        req.use_web_search
        if req.use_web_search is not None
        else (req.mode in search_default_modes)
    )
    search_task = None
    if do_search and settings.web_search_enabled:
        yield ("phase", "search")
        search_task = asyncio.create_task(web_search(req.message))

    targets = extract_targets(req.message, req.target)
    assess_modes = {"assess", "lab", "redteam", "ctf", "lab_offensive", "ciso"}
    do_assess = (
        req.use_net_assess
        if req.use_net_assess is not None
        else (req.mode == "assess" or bool(req.target) or (bool(targets) and req.mode in assess_modes))
    )
    assess_task = None
    if do_assess and settings.net_assess_enabled and (targets or req.target):
        authorized = bool(req.authorized_target) or req.mode in assess_modes
        yield ("phase", "assess")
        assess_task = asyncio.create_task(
            assess_from_request(
                req.message,
                target=req.target,
                authorized=authorized,
                allow_public=bool(req.authorized_target),
            )
        )

    tools_modes = {"assess", "lab", "redteam", "ctf", "lab_offensive", "ciso"}
    msg_lower = (req.message or "").lower()
    instruct_tools = any(
        k in msg_lower
        for k in (
            "run nmap", "run nikto", "run nuclei", "run zap", "use nmap", "use nuclei",
            "use zap", "use burp", "greenbone", "openvas", "acunetix", "tools:",
            "scan with", "probe with", "suite_guide", "phishing_url",
        )
    ) or bool(req.tools)
    do_tools = (
        req.use_local_tools
        if req.use_local_tools is not None
        else (
            settings.local_tools_auto
            and (
                req.mode == "assess"
                or bool(req.target)
                or instruct_tools
                or (bool(targets) and req.mode in tools_modes)
            )
        )
    )
    tools_task = None
    if do_tools and settings.local_tools_enabled:
        authorized = bool(req.authorized_target) or req.mode in tools_modes
        yield ("phase", "tools")
        tools_task = asyncio.create_task(
            run_security_tools(
                req.message,
                target=req.target,
                tools=req.tools,
                authorized=authorized,
                allow_public=bool(req.authorized_target),
                auto=not instruct_tools and not req.tools,
                include_heavy=settings.local_tools_allow_heavy or instruct_tools,
            )
        )

    if search_task is not None:
        try:
            search_payload = await search_task
        except Exception as exc:
            search_payload = {"query": req.message, "results": [], "provider": "error", "error": str(exc)}
        system_parts.append(SEARCH_BEHAVIOR_PROMPT)
        system_parts.append(format_search_context(search_payload))

    if assess_task is not None:
        try:
            assess_payload = await assess_task
        except Exception as exc:
            assess_payload = {"ok": False, "error": str(exc), "results": []}
        system_parts.append(ASSESS_MODE_PROMPT if req.mode != "assess" else "")
        system_parts.append(format_assess_context(assess_payload))
    elif do_assess and not (targets or req.target):
        system_parts.append(
            "## Network assessment\nNo target IP found. Ask for a lab/private IP "
            "(e.g. 192.168.x.x / 10.x) or fill the Target IP field."
        )

    if tools_task is not None:
        try:
            tools_payload = await tools_task
        except Exception as exc:
            tools_payload = {"ok": False, "error": str(exc), "runs": []}
        system_parts.append(TOOLS_BEHAVIOR_PROMPT)
        system_parts.append(format_tools_context(tools_payload))

    if req.use_rag:
        yield ("phase", "rag")
        top_k = MODE_RAG_TOP_K.get(req.mode, 3)
        context = await asyncio.to_thread(rag_engine.build_context, req.message, top_k)
        if context:
            system_parts.append(context)

    system_parts = [p for p in system_parts if p]
    messages: list[dict[str, str]] = [{"role": "system", "content": "\n\n".join(system_parts)}]
    for msg in req.history[-20:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": req.message})
    yield ("phase", "model")
    yield ("messages", messages)


@app.get("/api/health")
async def health():
    installed: list[str] = []
    if settings.model_backend == "ollama":
        backend_ready, installed = await fetch_ollama_tags()
        current = settings.ollama_model
        backend_status = "ready" if backend_ready and installed else "needs_model" if backend_ready else "offline"
    elif settings.model_backend == "openai_compat":
        backend_ready = await openai_compat_reachable()
        current = settings.openai_compat_model
        backend_status = "ready" if backend_ready else "offline"
    elif settings.model_backend == "hermes":
        backend_ready = await hermes_reachable()
        current = settings.hermes_model
        backend_status = "ready" if backend_ready else "offline"
    elif settings.model_backend == "unsloth":
        backend_ready = True
        current = settings.unsloth_adapter_dir if Path(settings.unsloth_adapter_dir).exists() else settings.unsloth_model
        backend_status = "ready" if model_client.unsloth_model_loaded else "loads_on_chat"
    else:
        backend_ready = True
        current = settings.hf_model
        backend_status = "ready" if model_client.hf_model_loaded else "loads_on_chat"
    return {
        "status": "ok",
        "backend": settings.model_backend,
        "model": current,
        "backend_ready": backend_ready,
        "backend_status": backend_status,
        "hf_model_loaded": model_client.hf_model_loaded if settings.model_backend == "huggingface" else None,
        "unsloth_model_loaded": model_client.unsloth_model_loaded if settings.model_backend == "unsloth" else None,
        "hf_token_set": bool(settings.hf_token),
        "installed_models": installed,
        "ollama_connected": backend_ready if settings.model_backend == "ollama" else None,
        "ollama_has_models": bool(installed) if settings.model_backend == "ollama" else None,
        "rag_documents": rag_engine.document_count(),
        "finetune": finetune_job.snapshot(),
        "integrations": {
            "hermes": True,
            "unsloth": True,
            "settings": True,
            "rag": True,
            "net_assess": settings.net_assess_enabled,
            "local_tools": settings.local_tools_enabled,
            "modes": list(MODE_RAG_TOP_K.keys()),
        },
    }


@app.get("/api/backend")
async def backend():
    return {
        "backend": settings.model_backend,
        "options": ["ollama", "openai_compat", "hermes", "unsloth", "huggingface"],
    }


@app.get("/api/backends/probe")
async def backends_probe():
    """Which AI backends are ready — used by UI auto-select."""
    return await probe_backends()


@app.post("/api/backend")
async def switch_backend(req: BackendSwitchRequest):
    settings.model_backend = req.backend
    update_env_value("MODEL_BACKEND", req.backend)
    return {"backend": settings.model_backend}


@app.post("/api/models/preload")
async def preload_model():
    if settings.model_backend not in ("huggingface", "unsloth"):
        raise HTTPException(status_code=400, detail="Preload only supported with HuggingFace or Unsloth backends.")

    async def stream():
        label = settings.hf_model if settings.model_backend == "huggingface" else settings.unsloth_model
        yield f"Loading `{label}`…\n"
        try:
            if settings.model_backend == "huggingface":
                await model_client.preload_huggingface()
            else:
                await model_client.preload_unsloth()
            yield "Model ready.\n"
        except Exception as exc:
            yield f"Load failed: {exc}\n"

    return StreamingResponse(stream(), media_type="text/plain; charset=utf-8")


@app.get("/api/settings")
async def get_settings():
    return public_settings()


@app.post("/api/settings")
async def update_settings(req: SettingsUpdateRequest):
    payload = req.model_dump(exclude_none=True)
    return apply_settings_patch(payload)


@app.get("/api/platform")
async def platform():
    """OS + LAN URLs + backend capabilities for Win/Linux/macOS hosts and mobile browsers."""
    return platform_info()


@app.get("/api/hermes/status")
async def hermes_status():
    """Hermes Agent reachability, models, and /v1/capabilities."""
    return await fetch_hermes_status()


@app.get("/api/search")
async def api_search(q: str = "", limit: int = 8):
    """Live cybersecurity web search (for UI/debug)."""
    query = (q or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Missing q")
    return await web_search(query, max_results=limit)


class AssessRequest(BaseModel):
    target: str = Field(min_length=1, max_length=253)
    message: str = ""
    authorized_target: bool = False


@app.post("/api/assess")
async def api_assess(req: AssessRequest):
    """Light authorized/lab host assessment (private ranges or owned public with confirm)."""
    if not settings.net_assess_enabled:
        raise HTTPException(status_code=400, detail="Network assess disabled")
    return await assess_from_request(
        req.message or f"assess {req.target}",
        target=req.target,
        authorized=req.authorized_target,
        allow_public=req.authorized_target,
    )


@app.get("/api/tools")
async def api_tools():
    """List built-in + PATH security tools and availability."""
    status = list_tools_status()
    status["enabled"] = settings.local_tools_enabled
    status["auto"] = settings.local_tools_auto
    status["allow_heavy"] = settings.local_tools_allow_heavy
    return status


class ToolsRunRequest(BaseModel):
    target: str | None = Field(default=None, max_length=253)
    message: str = ""
    tools: list[str] | None = None
    authorized_target: bool = False
    auto: bool = False


@app.post("/api/tools/run")
async def api_tools_run(req: ToolsRunRequest):
    """Run selected security tools against an authorized/lab target."""
    if not settings.local_tools_enabled:
        raise HTTPException(status_code=400, detail="Local tools disabled")
    return await run_security_tools(
        req.message or (f"run tools on {req.target}" if req.target else ""),
        target=req.target,
        tools=req.tools,
        authorized=req.authorized_target,
        allow_public=req.authorized_target,
        auto=req.auto and not req.tools,
        include_heavy=settings.local_tools_allow_heavy or bool(req.tools),
    )


@app.get("/api/finetune")
async def finetune_status():
    return finetune_job.snapshot()


@app.post("/api/finetune")
async def finetune_start(req: FinetuneStartRequest):
    if req.engine != "unsloth":
        raise HTTPException(status_code=400, detail="Only engine=unsloth is supported.")
    model = (req.model or settings.unsloth_model).strip()
    output = (req.output or settings.unsloth_adapter_dir).strip()
    ok = launch_unsloth_job(
        model=model,
        output=output,
        epochs=req.epochs,
        batch_size=req.batch_size,
    )
    if not ok:
        raise HTTPException(status_code=409, detail="A fine-tune job is already running.")
    return finetune_job.snapshot()


@app.get("/api/modes")
async def modes():
    return {
        "modes": list(MODE_RAG_TOP_K.keys()),
        "quick_prompts": QUICK_PROMPTS,
    }


@app.get("/api/status")
async def status():
    return {
        "rag_documents": rag_engine.document_count(),
        "rag_sources": rag_engine.list_sources(),
        "modes": list(MODE_RAG_TOP_K.keys()),
    }


@app.get("/api/models")
async def models():
    installed = await list_installed_models() if settings.model_backend == "ollama" else []
    if settings.model_backend == "ollama":
        current = settings.ollama_model
    elif settings.model_backend == "openai_compat":
        current = settings.openai_compat_model
    elif settings.model_backend == "hermes":
        current = settings.hermes_model
    elif settings.model_backend == "unsloth":
        adapter = Path(settings.unsloth_adapter_dir)
        current = str(adapter) if adapter.exists() else settings.unsloth_model
    else:
        current = settings.hf_model
    return {
        "backend": settings.model_backend,
        "current": current,
        "installed": installed,
        "recommended": RECOMMENDED_MODELS,
    }


@app.post("/api/models/switch")
async def switch_model(req: ModelSwitchRequest):
    if settings.model_backend != "ollama":
        raise HTTPException(status_code=400, detail="Model switching only supported with Ollama backend.")
    settings.ollama_model = req.model
    return {"current": settings.ollama_model}


@app.post("/api/models/pull")
async def pull_ollama_model(req: ModelPullRequest):
    if settings.model_backend != "ollama":
        raise HTTPException(status_code=400, detail="Model pull only supported with Ollama backend.")

    async def stream():
        async for line in pull_model(req.model):
            yield line

    return StreamingResponse(stream(), media_type="text/plain; charset=utf-8")


@app.post("/api/ingest")
async def ingest_knowledge() -> IngestResponse:
    count = rag_engine.ingest_directory(force=True)
    return IngestResponse(documents_ingested=count)


@app.get("/api/realtime")
async def realtime_feed():
    """Server-Sent Events: live health + tools pulse for the ops dock."""

    async def event_gen():
        while True:
            try:
                snap = await health()
                tools = list_tools_status()
                payload = {
                    "ts": asyncio.get_event_loop().time(),
                    "backend": snap.get("backend"),
                    "model": snap.get("model"),
                    "backend_ready": snap.get("backend_ready"),
                    "backend_status": snap.get("backend_status"),
                    "rag_documents": snap.get("rag_documents"),
                    "tools_available": tools.get("available_count"),
                    "tools_total": tools.get("count"),
                    "local_tools": settings.local_tools_enabled,
                    "net_assess": settings.net_assess_enabled,
                    "web_search": settings.web_search_enabled,
                }
                yield f"data: {json.dumps(payload)}\n\n"
            except Exception as exc:
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            await asyncio.sleep(4)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/chat")
async def chat(req: ChatRequest):
    guard = check_request(req.message)
    if not guard.allowed:
        async def refusal_stream():
            yield guard.reason or "Request blocked."
        return StreamingResponse(refusal_stream(), media_type="text/plain; charset=utf-8")

    response_headers: dict[str, str] = {}

    if settings.model_backend == "hermes":
        session_id = None if req.reset_hermes_session else (req.hermes_session_id or None)

        async def hermes_stream():
            messages = None
            yield "[[live:start]]"
            async for kind, payload in _iter_build_messages(req):
                if kind == "phase":
                    yield f"[[live:{payload}]]"
                elif kind == "messages":
                    messages = payload
            if not messages:
                yield "[[live:error]]"
                return
            async for token, sid in model_client.stream_chat_hermes(messages, session_id=session_id):
                if sid:
                    response_headers["X-Hermes-Session-Id"] = sid
                    yield f"[[hermes_session:{sid}]]"
                if token:
                    yield token
            yield "[[live:done]]"

        return StreamingResponse(
            hermes_stream(),
            media_type="text/plain; charset=utf-8",
            headers=response_headers,
        )

    async def event_stream():
        messages = None
        yield "[[live:start]]"
        async for kind, payload in _iter_build_messages(req):
            if kind == "phase":
                yield f"[[live:{payload}]]"
            elif kind == "messages":
                messages = payload
        if not messages:
            yield "[[live:error]]"
            return
        async for token in model_client.stream_chat(messages):
            yield token
        yield "[[live:done]]"

    return StreamingResponse(event_stream(), media_type="text/plain; charset=utf-8")


if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
