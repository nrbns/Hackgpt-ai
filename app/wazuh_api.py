"""API routes for Wazuh SIEM integration."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth import AuthUser
from app.commercial_api import require_user
from app.connectors import wazuh as wazuh_conn
from app.wazuh import list_agents
from app.wazuh import status as wazuh_status
from app.xdr import list_events

router = APIRouter(prefix="/api/wazuh", tags=["wazuh"])


@router.get("/status")
async def get_status(user: Annotated[AuthUser, Depends(require_user)]):
    st = wazuh_status()
    if st.get("configured"):
        st["ping"] = await wazuh_conn.ping()
    else:
        st["ping"] = {"ok": False, "error": "not_configured"}
    return st


@router.post("/sync")
async def trigger_sync(user: Annotated[AuthUser, Depends(require_user)]):
    from app.jobs import enqueue_job

    job = enqueue_job("wazuh_sync", {"user_id": user.id}, engine="auto")
    return {"job": job}


@router.get("/agents")
async def get_agents(user: Annotated[AuthUser, Depends(require_user)], limit: int = 100):
    return {"agents": list_agents(limit=limit)}


@router.get("/alerts")
async def get_alerts(user: Annotated[AuthUser, Depends(require_user)], limit: int = 50):
    return {"events": list_events(limit=limit, vendor="wazuh")}
