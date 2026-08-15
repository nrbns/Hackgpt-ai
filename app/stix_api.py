"""STIX 2.1 / TAXII 2.1 API — ingest, export, poll."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import AuthUser
from app.commercial_api import require_user
from app.config import settings
from app.stix_taxii import (
    export_stix_bundle,
    ingest_stix_bundle,
    parse_stix_bundle,
    taxii_poll_and_ingest,
    taxii_poll_collection,
)

router = APIRouter(prefix="/api/intel/stix", tags=["stix-taxii"])


class StixIngestRequest(BaseModel):
    bundle: dict[str, Any] | list = Field(..., description="STIX 2.1 bundle or objects list")
    also_vulns: bool = True


class TaxiiPollRequest(BaseModel):
    collection_url: str = ""
    api_root: str = ""
    collection_id: str = ""
    username: str = ""
    password: str = ""
    limit: int = 100
    ingest: bool = True


@router.get("/status")
async def stix_status(user: Annotated[AuthUser, Depends(require_user)]):
    root = (getattr(settings, "taxii_api_root", "") or "").strip()
    cid = (getattr(settings, "taxii_collection_id", "") or "").strip()
    return {
        "stix_version": "2.1",
        "taxii_version": "2.1",
        "ingest_path": "POST /api/intel/stix/ingest",
        "export_path": "GET /api/intel/stix/export",
        "taxii_poll_path": "POST /api/intel/stix/taxii/poll",
        "taxii_configured": bool(root and cid),
        "taxii_api_root": root or None,
        "taxii_collection_id": cid or None,
        "limits": "STIX 2.1 JSON only; TAXII pull (no server push channel yet)",
    }


@router.post("/ingest")
async def stix_ingest(req: StixIngestRequest, user: Annotated[AuthUser, Depends(require_user)]):
    try:
        return ingest_stix_bundle(user.id, req.bundle, also_vulns=req.also_vulns)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"STIX ingest failed: {exc}") from exc


@router.post("/parse")
async def stix_parse(req: StixIngestRequest, user: Annotated[AuthUser, Depends(require_user)]):
    """Dry-run parse — no DB writes."""
    return parse_stix_bundle(req.bundle)


@router.get("/export")
async def stix_export(user: Annotated[AuthUser, Depends(require_user)]):
    bundle = export_stix_bundle(user.id)
    return JSONResponse(content=bundle, media_type="application/stix+json;version=2.1")


@router.post("/taxii/poll")
async def stix_taxii_poll(req: TaxiiPollRequest, user: Annotated[AuthUser, Depends(require_user)]):
    params = dict(
        collection_url=req.collection_url,
        api_root=req.api_root,
        collection_id=req.collection_id,
        username=req.username,
        password=req.password,
        limit=req.limit,
    )
    if req.ingest:
        return await taxii_poll_and_ingest(user.id, **params)
    return await taxii_poll_collection(**params)
