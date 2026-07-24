"""Gap analysis catalog & assessment read/export APIs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from app.auth import AuthUser
from app.commercial_api import require_user
from app.gap_analysis import (
    ensure_gap_schema,
    export_gap_markdown,
    get_assessment,
    list_assessments,
    list_frameworks,
    load_framework,
)

router = APIRouter(prefix="/api", tags=["gap-analysis"])


@router.get("/frameworks")
async def frameworks():
    return {"frameworks": list_frameworks()}


@router.get("/frameworks/{framework_id}")
async def framework_detail(framework_id: str):
    try:
        return load_framework(framework_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/gap/assessments")
async def gap_list(
    user: Annotated[AuthUser, Depends(require_user)],
    engagement_id: str | None = None,
):
    ensure_gap_schema()
    return {"assessments": list_assessments(user.id, engagement_id)}


@router.get("/gap/assessments/{assessment_id}")
async def gap_get(assessment_id: str, user: Annotated[AuthUser, Depends(require_user)]):
    data = get_assessment(user.id, assessment_id)
    if not data:
        raise HTTPException(status_code=404, detail="Not found")
    return data


@router.get("/gap/assessments/{assessment_id}/export")
async def gap_export(assessment_id: str, user: Annotated[AuthUser, Depends(require_user)]):
    try:
        md = export_gap_markdown(user.id, assessment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PlainTextResponse(md, media_type="text/markdown; charset=utf-8")
