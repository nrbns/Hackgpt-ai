"""Archive API — download reports that survived clear / workspace reset."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from app.archive import find_archived_scan, list_archives, prototype_status
from app.auth import AuthUser
from app.commercial_api import require_user

router = APIRouter(prefix="/api/archive", tags=["archive"])


@router.get("/status")
async def archive_status(user: Annotated[AuthUser, Depends(require_user)]):
    st = prototype_status()
    st["archives"] = list_archives(user.id, limit=20)
    return st


@router.get("/scans")
async def archive_list(user: Annotated[AuthUser, Depends(require_user)], limit: int = 40):
    return {"archives": list_archives(user.id, limit=max(1, min(limit, 100)))}


@router.get("/scans/{scan_id}/report")
async def archive_report_md(scan_id: str, user: Annotated[AuthUser, Depends(require_user)]):
    path = find_archived_scan(scan_id)
    if not path:
        raise HTTPException(status_code=404, detail="Archived scan not found")
    report = path / "report.md"
    if not report.is_file():
        raise HTTPException(status_code=404, detail="Archived report.md missing")
    return PlainTextResponse(
        report.read_text(encoding="utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="securaiq-archive-{scan_id[:8]}.md"'},
    )


@router.get("/scans/{scan_id}/report.pdf")
async def archive_report_pdf(scan_id: str, user: Annotated[AuthUser, Depends(require_user)]):
    path = find_archived_scan(scan_id)
    if not path:
        raise HTTPException(status_code=404, detail="Archived scan not found")
    pdf = path / "report.pdf"
    if not pdf.is_file():
        raise HTTPException(status_code=404, detail="Archived PDF missing — open the Markdown archive instead")
    return FileResponse(
        path=str(pdf),
        media_type="application/pdf",
        filename=f"securaiq-archive-{scan_id[:8]}.pdf",
    )
