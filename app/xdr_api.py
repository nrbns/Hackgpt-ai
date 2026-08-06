"""API routes for XDR/EDR integrations — status, manual sync trigger,
normalized detections feed, and patch-compliance summary.

See app/xdr.py for the orchestration logic and app/connectors/{sophos,
crowdstrike,sentinelone,defender}.py for the per-vendor clients.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth import AuthUser
from app.commercial_api import require_user
from app.xdr import list_events, patch_compliance_summary
from app.xdr import status as xdr_status

router = APIRouter(prefix="/api/xdr", tags=["xdr"])


@router.get("/status")
async def get_status(user: Annotated[AuthUser, Depends(require_user)]):
    return {"vendors": xdr_status()}


@router.post("/sync")
async def trigger_sync(user: Annotated[AuthUser, Depends(require_user)]):
    from app.jobs import enqueue_job

    job = enqueue_job("xdr_sync", {"user_id": user.id})
    return {"job": job}


@router.get("/detections")
async def get_detections(
    user: Annotated[AuthUser, Depends(require_user)],
    limit: int = 100,
    vendor: str | None = None,
    kind: str | None = None,
):
    return {"events": list_events(limit=limit, vendor=vendor, kind=kind)}


@router.get("/patches")
async def get_patch_compliance(user: Annotated[AuthUser, Depends(require_user)]):
    return patch_compliance_summary()
