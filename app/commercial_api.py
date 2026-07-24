"""Commercial workspace APIs: auth, engagements, chats, files, memory, export, audit."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.auth import (
    AuthUser,
    create_api_key,
    ensure_bootstrap_admin,
    login,
    logout,
    register_user,
    resolve_user,
)
from app.config import settings
from app.db import get_conn, now as db_now
from app.export_report import export_chat_markdown, export_engagement_summary
from app.model_router import route_task
from app.uploads import list_files, save_upload
from app.workspace import (
    append_message,
    create_chat,
    create_engagement,
    delete_chat,
    get_chat,
    list_audit,
    list_chats,
    list_engagements,
    list_memories,
    list_messages,
    set_memory,
    update_engagement,
)

router = APIRouter(prefix="/api", tags=["workspace"])


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str = Field(min_length=8)


class EngagementCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scope_notes: str = ""


class EngagementUpdate(BaseModel):
    name: str | None = None
    scope_notes: str | None = None


class ChatCreate(BaseModel):
    title: str = "New chat"
    mode: str = "default"
    engagement_id: str | None = None


class MessageCreate(BaseModel):
    role: str
    content: str


class MemorySet(BaseModel):
    key: str
    value: str


class RouteRequest(BaseModel):
    message: str
    mode: str = "default"


class ApiKeyCreate(BaseModel):
    name: str = "default"


def current_user(
    authorization: Annotated[str | None, Header()] = None,
    x_securaiq_key: Annotated[str | None, Header(alias="X-SecuraIQ-Key")] = None,
    x_hackgpt_key: Annotated[str | None, Header(alias="X-HackGPT-Key")] = None,
) -> AuthUser | None:
    return resolve_user(authorization, x_securaiq_key or x_hackgpt_key)


def require_user(user: Annotated[AuthUser | None, Depends(current_user)]) -> AuthUser:
    if not settings.auth_enabled:
        # Anonymous local mode — synthetic user for workspace when auth off
        if user:
            return user
        return AuthUser(id="local", username="local", role="admin")
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


@router.get("/auth/status")
async def auth_status(user: Annotated[AuthUser | None, Depends(current_user)]):
    return {
        "auth_enabled": settings.auth_enabled,
        "allow_register": settings.auth_allow_register,
        "authenticated": bool(user) or not settings.auth_enabled,
        "user": {"id": user.id, "username": user.username, "role": user.role} if user else (
            {"id": "local", "username": "local", "role": "admin"} if not settings.auth_enabled else None
        ),
    }


@router.post("/auth/register")
async def auth_register(req: RegisterRequest):
    if not settings.auth_enabled:
        raise HTTPException(status_code=400, detail="Auth disabled")
    if not settings.auth_allow_register:
        raise HTTPException(status_code=403, detail="Registration closed")
    try:
        u = register_user(req.username, req.password)
        user, token = login(req.username, req.password)
        return {"user": {"id": user.id, "username": user.username, "role": user.role}, "token": token}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/auth/login")
async def auth_login(req: LoginRequest):
    if not settings.auth_enabled:
        raise HTTPException(status_code=400, detail="Auth disabled — set AUTH_ENABLED=true")
    try:
        user, token = login(req.username, req.password)
        return {"user": {"id": user.id, "username": user.username, "role": user.role}, "token": token}
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/auth/logout")
async def auth_logout(authorization: Annotated[str | None, Header()] = None):
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    logout(token)
    return {"ok": True}


@router.post("/auth/api-keys")
async def auth_api_key(req: ApiKeyCreate, user: Annotated[AuthUser, Depends(require_user)]):
    if user.id == "local" and not settings.auth_enabled:
        raise HTTPException(status_code=400, detail="Enable AUTH_ENABLED to create API keys")
    raw, meta = create_api_key(user.id, req.name)
    return {"api_key": raw, **meta, "note": "Store this key now — it will not be shown again."}


@router.get("/engagements")
async def eng_list(user: Annotated[AuthUser, Depends(require_user)]):
    return {"engagements": list_engagements(user.id)}


@router.post("/engagements")
async def eng_create(req: EngagementCreate, user: Annotated[AuthUser, Depends(require_user)]):
    return create_engagement(user.id, req.name, req.scope_notes)


@router.patch("/engagements/{engagement_id}")
async def eng_update(engagement_id: str, req: EngagementUpdate, user: Annotated[AuthUser, Depends(require_user)]):
    out = update_engagement(user.id, engagement_id, req.name, req.scope_notes)
    if not out:
        raise HTTPException(status_code=404, detail="Not found")
    return out


@router.get("/chats")
async def chats_list(user: Annotated[AuthUser, Depends(require_user)], engagement_id: str | None = None):
    return {"chats": list_chats(user.id, engagement_id)}


@router.post("/chats")
async def chats_create(req: ChatCreate, user: Annotated[AuthUser, Depends(require_user)]):
    return create_chat(user.id, req.title, req.mode, req.engagement_id)


@router.get("/chats/{chat_id}")
async def chats_get(chat_id: str, user: Annotated[AuthUser, Depends(require_user)]):
    chat = get_chat(user.id, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Not found")
    return {"chat": chat, "messages": list_messages(user.id, chat_id)}


@router.delete("/chats/{chat_id}")
async def chats_delete(chat_id: str, user: Annotated[AuthUser, Depends(require_user)]):
    if not delete_chat(user.id, chat_id):
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


@router.post("/chats/{chat_id}/messages")
async def chats_message(chat_id: str, req: MessageCreate, user: Annotated[AuthUser, Depends(require_user)]):
    if req.role not in {"user", "assistant", "system"}:
        raise HTTPException(status_code=400, detail="Invalid role")
    msg = append_message(user.id, chat_id, req.role, req.content)
    if not msg:
        raise HTTPException(status_code=404, detail="Chat not found")
    return msg


@router.get("/engagements/{engagement_id}/memories")
async def mem_list(engagement_id: str, user: Annotated[AuthUser, Depends(require_user)]):
    return {"memories": list_memories(user.id, engagement_id)}


@router.post("/engagements/{engagement_id}/memories")
async def mem_set(engagement_id: str, req: MemorySet, user: Annotated[AuthUser, Depends(require_user)]):
    out = set_memory(user.id, engagement_id, req.key, req.value)
    if not out:
        raise HTTPException(status_code=404, detail="Engagement not found")
    return out


@router.post("/files")
async def files_upload(
    user: Annotated[AuthUser, Depends(require_user)],
    file: UploadFile = File(...),
    engagement_id: str | None = None,
    ingest: bool = True,
):
    data = await file.read()
    try:
        return save_upload(user.id, file.filename or "upload.bin", data, engagement_id, ingest)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/files")
async def files_list(user: Annotated[AuthUser, Depends(require_user)], engagement_id: str | None = None):
    return {"files": list_files(user.id, engagement_id)}


@router.get("/chats/{chat_id}/export")
async def chat_export(chat_id: str, user: Annotated[AuthUser, Depends(require_user)]):
    try:
        md = export_chat_markdown(user.id, chat_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PlainTextResponse(md, media_type="text/markdown; charset=utf-8")


@router.get("/engagements/{engagement_id}/export")
async def eng_export(engagement_id: str, user: Annotated[AuthUser, Depends(require_user)]):
    try:
        return export_engagement_summary(user.id, engagement_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/router")
async def model_route(req: RouteRequest):
    return route_task(req.message, req.mode)


@router.get("/audit")
async def audit_list(user: Annotated[AuthUser, Depends(require_user)], limit: int = 100):
    if settings.auth_enabled and user.role != "admin" and user.id != "local":
        raise HTTPException(status_code=403, detail="Admin only")
    return {"events": list_audit(limit)}


def bootstrap_auth() -> None:
    if settings.auth_enabled:
        ensure_bootstrap_admin()
        return
    c = get_conn()
    row = c.execute("SELECT id FROM users WHERE id = 'local'").fetchone()
    if not row:
        c.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
            ("local", "local", "local-open-mode", "admin", db_now()),
        )
        c.commit()
