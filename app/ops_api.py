"""API routes for SOC, threat intel, reports catalog, and global search."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import AuthUser
from app.commercial_api import require_user
from app.ops import (
    add_intel_watch,
    create_incident,
    delete_incident,
    delete_intel_watch,
    global_search,
    list_incidents,
    list_intel_watch,
    purge_demo_seed,
    reports_catalog,
    soc_overview,
    update_incident,
)

router = APIRouter(prefix="/api", tags=["ops"])


class IncidentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    severity: str = "high"
    status: str = "open"
    source: str = "manual"
    owner: str = ""
    playbook_id: str | None = None
    summary: str = ""
    engagement_id: str | None = None


class IncidentUpdate(BaseModel):
    title: str | None = None
    severity: str | None = None
    status: str | None = None
    source: str | None = None
    owner: str | None = None
    playbook_id: str | None = None
    summary: str | None = None
    engagement_id: str | None = None


class IntelWatchCreate(BaseModel):
    kind: str = "cve"
    value: str = Field(min_length=1, max_length=300)
    notes: str = ""


@router.get("/soc")
async def soc(user: Annotated[AuthUser, Depends(require_user)]):
    return soc_overview(user.id)


@router.get("/incidents")
async def incidents_list(
    user: Annotated[AuthUser, Depends(require_user)],
    engagement_id: str | None = None,
    status: str | None = None,
):
    purge_demo_seed(user.id)
    return {"incidents": list_incidents(user.id, engagement_id=engagement_id, status=status)}


@router.post("/incidents")
async def incidents_create(req: IncidentCreate, user: Annotated[AuthUser, Depends(require_user)]):
    return create_incident(user.id, **req.model_dump())


@router.patch("/incidents/{incident_id}")
async def incidents_update(
    incident_id: str, req: IncidentUpdate, user: Annotated[AuthUser, Depends(require_user)]
):
    out = update_incident(user.id, incident_id, req.model_dump(exclude_none=True))
    if not out:
        raise HTTPException(status_code=404, detail="Not found")
    return out


@router.delete("/incidents/{incident_id}")
async def incidents_delete(incident_id: str, user: Annotated[AuthUser, Depends(require_user)]):
    if not delete_incident(user.id, incident_id):
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


@router.get("/intel/watch")
async def intel_list(user: Annotated[AuthUser, Depends(require_user)]):
    return {"watch": list_intel_watch(user.id)}


@router.post("/intel/watch")
async def intel_add(req: IntelWatchCreate, user: Annotated[AuthUser, Depends(require_user)]):
    return add_intel_watch(user.id, kind=req.kind, value=req.value, notes=req.notes)


@router.delete("/intel/watch/{watch_id}")
async def intel_delete(watch_id: str, user: Annotated[AuthUser, Depends(require_user)]):
    if not delete_intel_watch(user.id, watch_id):
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


@router.get("/reports")
async def reports(user: Annotated[AuthUser, Depends(require_user)]):
    return reports_catalog(user.id)


@router.get("/search")
async def search(q: str, user: Annotated[AuthUser, Depends(require_user)]):
    return global_search(user.id, q)
