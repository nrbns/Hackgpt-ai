from __future__ import annotations

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
    BLUETEAM_MODE_PROMPT,
    CTF_MODE_PROMPT,
    LAB_MODE_PROMPT,
    MALWARE_ANALYSIS_MODE_PROMPT,
    REDTEAM_MODE_PROMPT,
    SYSTEM_PROMPT,
)
from app.backends import openai_compat_reachable
from app.env_persist import update_env_value
from app.ollama_models import RECOMMENDED_MODELS, list_installed_models, ollama_reachable, pull_model
from app.rag import rag_engine

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        count = rag_engine.ingest_directory()
        if count:
            print(f"RAG: indexed {count} knowledge documents.")
    except Exception as exc:
        print(f"RAG ingest skipped: {exc}")
    if settings.model_backend == "huggingface":
        print(f"HuggingFace backend: {settings.hf_model} (loads on first chat)")
    yield


app = FastAPI(title="PentestGPT", version="1.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=16000)
    history: list[ChatMessage] = Field(default_factory=list)
    mode: Literal["default", "ctf", "lab", "redteam", "blueteam", "malware"] = "default"
    use_rag: bool = True


class IngestResponse(BaseModel):
    documents_ingested: int


class ModelSwitchRequest(BaseModel):
    model: str = Field(min_length=1, max_length=128)


class ModelPullRequest(BaseModel):
    model: str = Field(min_length=1, max_length=128)


class BackendSwitchRequest(BaseModel):
    backend: Literal["ollama", "openai_compat", "huggingface"]


MODE_RAG_TOP_K = {
    "default": 3,
    "ctf": 3,
    "lab": 4,
    "redteam": 4,
    "blueteam": 5,
    "malware": 5,
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
}


def _build_messages(req: ChatRequest) -> list[dict[str, str]]:
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

    if req.use_rag:
        top_k = MODE_RAG_TOP_K.get(req.mode, 3)
        context = rag_engine.build_context(req.message, top_k=top_k)
        if context:
            system_parts.append(context)

    messages: list[dict[str, str]] = [{"role": "system", "content": "\n\n".join(system_parts)}]

    for msg in req.history[-20:]:
        messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": req.message})
    return messages


@app.get("/api/health")
async def health():
    installed = await list_installed_models() if settings.model_backend == "ollama" else []
    if settings.model_backend == "ollama":
        backend_ready = await ollama_reachable()
        current = settings.ollama_model
        backend_status = "ready" if backend_ready and installed else "needs_model" if backend_ready else "offline"
    elif settings.model_backend == "openai_compat":
        backend_ready = await openai_compat_reachable()
        current = settings.openai_compat_model
        backend_status = "ready" if backend_ready else "offline"
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
        "installed_models": installed,
        "ollama_connected": backend_ready if settings.model_backend == "ollama" else None,
        "ollama_has_models": bool(installed) if settings.model_backend == "ollama" else None,
        "rag_documents": rag_engine.document_count(),
    }


@app.get("/api/backend")
async def backend():
    return {
        "backend": settings.model_backend,
        "options": ["ollama", "openai_compat", "huggingface"],
    }


@app.post("/api/backend")
async def switch_backend(req: BackendSwitchRequest):
    settings.model_backend = req.backend
    update_env_value("MODEL_BACKEND", req.backend)
    return {"backend": settings.model_backend}


@app.post("/api/models/preload")
async def preload_model():
    if settings.model_backend != "huggingface":
        raise HTTPException(status_code=400, detail="Preload only supported with HuggingFace backend.")

    async def stream():
        yield f"Loading `{settings.hf_model}`…\n"
        try:
            await model_client.preload_huggingface()
            yield "Model ready.\n"
        except Exception as exc:
            yield f"Load failed: {exc}\n"

    return StreamingResponse(stream(), media_type="text/plain")


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

    return StreamingResponse(stream(), media_type="text/plain")


@app.post("/api/ingest")
async def ingest_knowledge() -> IngestResponse:
    count = rag_engine.ingest_directory()
    return IngestResponse(documents_ingested=count)


@app.post("/api/chat")
async def chat(req: ChatRequest):
    guard = check_request(req.message)
    if not guard.allowed:
        async def refusal_stream():
            yield guard.reason or "Request blocked."
        return StreamingResponse(refusal_stream(), media_type="text/plain")

    messages = _build_messages(req)

    async def event_stream():
        async for token in model_client.stream_chat(messages):
            yield token

    return StreamingResponse(event_stream(), media_type="text/plain")


if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
