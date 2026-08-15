"""API routes for SonarQube live sync + status."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth import AuthUser
from app.commercial_api import require_user
from app.connectors import sonarqube as sonar_conn
from app.sonarqube import status as sonar_status

router = APIRouter(prefix="/api/sonarqube", tags=["sonarqube"])


@router.get("/status")
async def get_status(user: Annotated[AuthUser, Depends(require_user)]):
    st = sonar_status()
    st["ping"] = await sonar_conn.ping() if st.get("configured") else {"ok": False, "error": "not_configured"}
    return st


@router.post("/sync")
async def trigger_sync(user: Annotated[AuthUser, Depends(require_user)]):
    from app.jobs import enqueue_job

    job = enqueue_job("sonarqube_sync", {"user_id": user.id}, engine="auto")
    return {"job": job, "ok": True}


@router.post("/test")
async def test_connection(user: Annotated[AuthUser, Depends(require_user)]):
    return await sonar_conn.ping()
