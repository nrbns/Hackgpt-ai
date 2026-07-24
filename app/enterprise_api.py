"""Enterprise workflow APIs: risks, assets, vulnerabilities, remediations."""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.auth import AuthUser
from app.commercial_api import require_user
from app.enterprise import (
    create_asset,
    create_campaign,
    create_playbook,
    create_remediation,
    create_risk,
    delete_asset,
    delete_campaign,
    delete_playbook,
    delete_risk,
    enterprise_dashboard,
    evidence_from_files,
    export_risk_markdown,
    export_vuln_markdown,
    import_vulnerabilities,
    list_assets,
    list_campaigns,
    list_playbooks,
    list_remediations,
    list_risks,
    list_vulnerabilities,
    update_asset,
    update_campaign,
    update_playbook,
    update_remediation,
    update_risk,
    update_vulnerability,
)
from app.gap_analysis import ensure_gap_schema, run_gap_analysis

router = APIRouter(prefix="/api", tags=["enterprise"])


class AssetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    asset_type: str = "server"
    criticality: str = "medium"
    owner: str = ""
    notes: str = ""
    engagement_id: str | None = None


class AssetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    asset_type: str | None = None
    criticality: str | None = None
    owner: str | None = None
    notes: str | None = None
    engagement_id: str | None = None


class RiskCreate(BaseModel):
    threat: str = Field(min_length=1, max_length=500)
    vulnerability: str = ""
    asset_name: str = ""
    asset_id: str | None = None
    impact: int = Field(default=3, ge=1, le=5)
    likelihood: int = Field(default=3, ge=1, le=5)
    owner: str = ""
    mitigation: str = ""
    status: str = "open"
    engagement_id: str | None = None


class RiskUpdate(BaseModel):
    threat: str | None = None
    vulnerability: str | None = None
    asset_name: str | None = None
    impact: int | None = Field(default=None, ge=1, le=5)
    likelihood: int | None = Field(default=None, ge=1, le=5)
    owner: str | None = None
    mitigation: str | None = None
    status: str | None = None


class VulnUpdate(BaseModel):
    status: str | None = None
    owner: str | None = None
    sla_due: str | None = None
    severity: str | None = None
    title: str | None = None
    asset_name: str | None = None
    cve: str | None = None


class RemediationUpdate(BaseModel):
    status: str | None = None
    owner: str | None = None
    due_date: str | None = None
    notes: str | None = None


class RemediationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    control_id: str = "MC"
    owner: str = ""
    due_date: str = ""
    recommendation: str = ""
    engagement_id: str | None = None
    assessment_id: str | None = None


class GapRunStructured(BaseModel):
    framework_id: str
    evidence: str = ""
    title: str = "Gap assessment"
    engagement_id: str | None = None
    file_ids: list[str] = Field(default_factory=list)
    overrides: dict[str, str] | None = None


class PlaybookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    category: str = "ir"
    severity: str = "high"
    steps: str = ""
    status: str = "ready"
    owner: str = ""
    engagement_id: str | None = None


class PlaybookUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    severity: str | None = None
    steps: str | None = None
    status: str | None = None
    owner: str | None = None
    engagement_id: str | None = None


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    campaign_type: str = "phishing_sim"
    audience: str = ""
    status: str = "planned"
    sent_count: int = Field(default=0, ge=0)
    click_count: int = Field(default=0, ge=0)
    report_count: int = Field(default=0, ge=0)
    notes: str = ""
    engagement_id: str | None = None


class CampaignUpdate(BaseModel):
    name: str | None = None
    campaign_type: str | None = None
    audience: str | None = None
    status: str | None = None
    sent_count: int | None = Field(default=None, ge=0)
    click_count: int | None = Field(default=None, ge=0)
    report_count: int | None = Field(default=None, ge=0)
    notes: str | None = None
    engagement_id: str | None = None


@router.get("/dashboard")
async def dashboard(user: Annotated[AuthUser, Depends(require_user)]):
    ensure_gap_schema()
    return enterprise_dashboard(user.id)


class WorkspaceResetRequest(BaseModel):
    clear_rag: bool = False
    confirm: bool = False


@router.post("/workspace/reset")
async def workspace_reset(req: WorkspaceResetRequest, user: Annotated[AuthUser, Depends(require_user)]):
    """Wipe operational data for the current user. Starts Mission Control from zero."""
    if not req.confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true to reset workspace")
    from app.enterprise import reset_workspace

    return reset_workspace(user.id, clear_rag=req.clear_rag)


@router.get("/assets")
async def assets_list(user: Annotated[AuthUser, Depends(require_user)], engagement_id: str | None = None):
    return {"assets": list_assets(user.id, engagement_id)}


@router.post("/assets")
async def assets_create(req: AssetCreate, user: Annotated[AuthUser, Depends(require_user)]):
    return create_asset(
        user.id,
        req.name,
        asset_type=req.asset_type,
        criticality=req.criticality,
        owner=req.owner,
        notes=req.notes,
        engagement_id=req.engagement_id,
    )


@router.patch("/assets/{asset_id}")
async def assets_update(asset_id: str, req: AssetUpdate, user: Annotated[AuthUser, Depends(require_user)]):
    out = update_asset(user.id, asset_id, req.model_dump(exclude_none=True))
    if not out:
        raise HTTPException(status_code=404, detail="Not found")
    return out


@router.delete("/assets/{asset_id}")
async def assets_delete(asset_id: str, user: Annotated[AuthUser, Depends(require_user)]):
    if not delete_asset(user.id, asset_id):
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


@router.get("/risks")
async def risks_list(
    user: Annotated[AuthUser, Depends(require_user)],
    engagement_id: str | None = None,
    status: str | None = None,
):
    return {"risks": list_risks(user.id, engagement_id=engagement_id, status=status)}


@router.get("/risks/export")
async def risks_export(user: Annotated[AuthUser, Depends(require_user)], engagement_id: str | None = None):
    return PlainTextResponse(
        export_risk_markdown(user.id, engagement_id),
        media_type="text/markdown; charset=utf-8",
    )


@router.post("/risks")
async def risks_create(req: RiskCreate, user: Annotated[AuthUser, Depends(require_user)]):
    return create_risk(user.id, **req.model_dump())


@router.patch("/risks/{risk_id}")
async def risks_update(risk_id: str, req: RiskUpdate, user: Annotated[AuthUser, Depends(require_user)]):
    out = update_risk(user.id, risk_id, req.model_dump(exclude_none=True))
    if not out:
        raise HTTPException(status_code=404, detail="Not found")
    return out


@router.delete("/risks/{risk_id}")
async def risks_delete(risk_id: str, user: Annotated[AuthUser, Depends(require_user)]):
    if not delete_risk(user.id, risk_id):
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


@router.get("/vulnerabilities")
async def vulns_list(
    user: Annotated[AuthUser, Depends(require_user)],
    engagement_id: str | None = None,
    status: str | None = None,
):
    return {"vulnerabilities": list_vulnerabilities(user.id, engagement_id=engagement_id, status=status)}


@router.get("/vulnerabilities/export")
async def vulns_export(user: Annotated[AuthUser, Depends(require_user)], engagement_id: str | None = None):
    return PlainTextResponse(
        export_vuln_markdown(user.id, engagement_id),
        media_type="text/markdown; charset=utf-8",
    )


@router.post("/vulnerabilities/import")
async def vulns_import(
    user: Annotated[AuthUser, Depends(require_user)],
    file: UploadFile = File(...),
    engagement_id: str | None = None,
):
    data = await file.read()
    try:
        return import_vulnerabilities(
            user.id,
            content=data,
            filename=file.filename or "import.csv",
            engagement_id=engagement_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Import failed: {exc}") from exc


@router.get("/vulnerabilities/samples")
async def vulns_samples(user: Annotated[AuthUser, Depends(require_user)]):
    """List authorized lab scanner fixtures under data/samples/."""
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "data" / "samples"
    items = []
    if root.is_dir():
        for p in sorted(root.glob("*-lab.json")):
            items.append({"id": p.stem, "filename": p.name, "path": f"data/samples/{p.name}"})
    return {
        "samples": items,
        "hint": "Lab fixtures only (Trivy/Semgrep/Gitleaks). Import into authorized workspace.",
    }


@router.post("/vulnerabilities/samples/{sample_id}/import")
async def vulns_sample_import(
    sample_id: str,
    user: Annotated[AuthUser, Depends(require_user)],
    engagement_id: str | None = None,
):
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "data" / "samples"
    # prevent path traversal
    safe = re.sub(r"[^a-zA-Z0-9._-]", "", sample_id)
    candidates = [
        root / f"{safe}.json",
        root / f"{safe}-lab.json",
        root / safe,
    ]
    path = next((p for p in candidates if p.is_file() and p.parent.resolve() == root.resolve()), None)
    if not path:
        raise HTTPException(status_code=404, detail="Sample not found")
    try:
        return import_vulnerabilities(
            user.id,
            content=path.read_bytes(),
            filename=path.name,
            engagement_id=engagement_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/vulnerabilities/{vuln_id}")
async def vulns_update(vuln_id: str, req: VulnUpdate, user: Annotated[AuthUser, Depends(require_user)]):
    out = update_vulnerability(user.id, vuln_id, req.model_dump(exclude_none=True))
    if not out:
        raise HTTPException(status_code=404, detail="Not found")
    return out


@router.get("/gap/remediations")
async def rem_list(
    user: Annotated[AuthUser, Depends(require_user)],
    assessment_id: str | None = None,
    engagement_id: str | None = None,
    status: str | None = None,
):
    return {
        "remediations": list_remediations(
            user.id, assessment_id=assessment_id, engagement_id=engagement_id, status=status
        )
    }


@router.post("/gap/remediations")
async def rem_create(req: RemediationCreate, user: Annotated[AuthUser, Depends(require_user)]):
    return create_remediation(user.id, **req.model_dump())


@router.patch("/gap/remediations/{rem_id}")
async def rem_update(rem_id: str, req: RemediationUpdate, user: Annotated[AuthUser, Depends(require_user)]):
    out = update_remediation(user.id, rem_id, req.model_dump(exclude_none=True))
    if not out:
        raise HTTPException(status_code=404, detail="Not found")
    return out


@router.get("/playbooks")
async def playbooks_list(
    user: Annotated[AuthUser, Depends(require_user)],
    engagement_id: str | None = None,
):
    return {"playbooks": list_playbooks(user.id, engagement_id)}


@router.post("/playbooks")
async def playbooks_create(req: PlaybookCreate, user: Annotated[AuthUser, Depends(require_user)]):
    return create_playbook(user.id, **req.model_dump())


@router.patch("/playbooks/{playbook_id}")
async def playbooks_update(
    playbook_id: str, req: PlaybookUpdate, user: Annotated[AuthUser, Depends(require_user)]
):
    out = update_playbook(user.id, playbook_id, req.model_dump(exclude_none=True))
    if not out:
        raise HTTPException(status_code=404, detail="Not found")
    return out


@router.delete("/playbooks/{playbook_id}")
async def playbooks_delete(playbook_id: str, user: Annotated[AuthUser, Depends(require_user)]):
    if not delete_playbook(user.id, playbook_id):
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


@router.get("/campaigns")
async def campaigns_list(
    user: Annotated[AuthUser, Depends(require_user)],
    engagement_id: str | None = None,
):
    return {"campaigns": list_campaigns(user.id, engagement_id)}


@router.post("/campaigns")
async def campaigns_create(req: CampaignCreate, user: Annotated[AuthUser, Depends(require_user)]):
    return create_campaign(user.id, **req.model_dump())


@router.patch("/campaigns/{campaign_id}")
async def campaigns_update(
    campaign_id: str, req: CampaignUpdate, user: Annotated[AuthUser, Depends(require_user)]
):
    out = update_campaign(user.id, campaign_id, req.model_dump(exclude_none=True))
    if not out:
        raise HTTPException(status_code=404, detail="Not found")
    return out


@router.delete("/campaigns/{campaign_id}")
async def campaigns_delete(campaign_id: str, user: Annotated[AuthUser, Depends(require_user)]):
    if not delete_campaign(user.id, campaign_id):
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


@router.post("/gap/run")
async def gap_run_structured(req: GapRunStructured, user: Annotated[AuthUser, Depends(require_user)]):
    """Structured gap workflow: evidence text + optional uploaded file IDs."""
    ensure_gap_schema()
    evidence = (req.evidence or "").strip()
    if req.file_ids:
        file_ev = evidence_from_files(user.id, req.file_ids)
        evidence = (evidence + "\n\n" + file_ev).strip() if evidence else file_ev
    if not evidence:
        raise HTTPException(status_code=400, detail="Provide evidence text and/or file_ids")
    try:
        return run_gap_analysis(
            framework_id=req.framework_id,
            evidence=evidence,
            title=req.title,
            engagement_id=req.engagement_id,
            user_id=user.id,
            overrides=req.overrides,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
