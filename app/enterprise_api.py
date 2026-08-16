"""Enterprise workflow APIs: risks, assets, vulnerabilities, remediations."""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.auth import AuthUser
from app.commercial_api import require_user
from app.rbac import require_perm
from app.services.tenancy import resolve_request_org
from app.services.assets import (
    create_asset,
    delete_asset,
    list_assets,
    update_asset,
)
from app.services.findings import (
    get_vulnerability,
    import_vulnerabilities,
    list_vulnerabilities,
    triage_vulnerability,
    update_vulnerability,
)
from app.services.risk import (
    compute_risk_score,
    create_risk,
    delete_risk,
    explain_risk_score,
    list_risks,
    update_risk,
)
from app.services.investigation import investigate_top_assets
from app.enterprise import (
    create_campaign,
    create_playbook,
    create_remediation,
    delete_campaign,
    delete_playbook,
    enterprise_dashboard,
    evidence_from_files,
    export_risk_markdown,
    export_vuln_markdown,
    list_campaigns,
    list_playbooks,
    list_remediations,
    update_campaign,
    update_playbook,
    update_remediation,
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


@router.get("/dashboard/brief")
async def dashboard_brief(user: Annotated[AuthUser, Depends(require_user)]):
    """Morning Mission Control brief (fast rules engine; model optional later)."""
    ensure_gap_schema()
    dash = enterprise_dashboard(user.id)
    brief = dash.get("morning_brief") or {}
    return {
        "user": user.username,
        "organization": (dash.get("mission_control") or {}).get("organization"),
        "brief": brief,
        "scores": {
            "security": dash.get("security_index"),
            "compliance": dash.get("compliance_score"),
            "critical": dash.get("vulnerabilities_critical_high"),
            "risks": dash.get("risks_open"),
            "incidents": dash.get("incidents_open"),
        },
        "tasks": (dash.get("work_queue") or [])[:5],
    }


class WorkspaceResetRequest(BaseModel):
    clear_rag: bool = False
    confirm: bool = False
    confirm_code: str | None = None


@router.post("/workspace/reset/request-code")
async def workspace_reset_request_code(user: Annotated[AuthUser, Depends(require_user)]):
    """Step 1 of destructive-action approval when AUTH is enabled.

    In open local mode (AUTH_ENABLED=false) the code is also returned in the
    response so the UI can complete a one-click reset on localhost without
    digging through notifications.
    """
    from app.approvals import request_approval
    from app.config import settings as _settings

    result = request_approval(user.id, "workspace_reset", {})
    if not _settings.auth_enabled:
        # Local open mode only — code is still required by /workspace/reset
        from app.db import get_conn

        row = get_conn().execute(
            "SELECT code FROM action_approvals WHERE user_id = ? AND action = ? "
            "AND consumed_at IS NULL ORDER BY created_at DESC LIMIT 1",
            (user.id, "workspace_reset"),
        ).fetchone()
        if row:
            result = {**result, "confirm_code": row["code"] if hasattr(row, "keys") else row[0]}
    return result


@router.post("/workspace/reset")
async def workspace_reset(req: WorkspaceResetRequest, user: Annotated[AuthUser, Depends(require_user)]):
    """Wipe operational data for the current user. Starts Mission Control from zero."""
    from app.approvals import verify_and_consume
    from app.config import settings as _settings
    from app.enterprise import reset_workspace

    code = (req.confirm_code or "").strip()
    if not code or not verify_and_consume(user.id, "workspace_reset", code):
        raise HTTPException(
            status_code=400,
            detail=(
                "Missing or invalid confirmation code. Call POST /api/workspace/reset/request-code first, "
                + (
                    "check your notifications for the code, then resubmit with confirm_code set."
                    if _settings.auth_enabled
                    else "then resubmit with confirm_code (returned in local open mode)."
                )
            ),
        )
    return reset_workspace(user.id, clear_rag=req.clear_rag)


class InvestigateRequest(BaseModel):
    limit: int = Field(default=5, ge=1, le=25)
    engagement_id: str | None = None
    org_id: str | None = None


class RiskScoreRequest(BaseModel):
    cvss: float | None = None
    exploitability: float | None = None
    exposure: float | None = None
    asset_criticality: str | None = "medium"
    threat_intel: float | None = None
    confidence: float | None = None


@router.get("/assets")
async def assets_list(
    user: Annotated[AuthUser, Depends(require_user)],
    engagement_id: str | None = None,
    org_id: str | None = None,
    x_securaiq_org: str | None = Header(default=None, alias="X-SecuraIQ-Org"),
):
    oid = resolve_request_org(user, org_id=org_id, header_org=x_securaiq_org)
    require_perm(user, "asset.read", org_id=oid)
    return {"assets": list_assets(user.id, engagement_id, org_id=oid), "org_id": oid}


@router.post("/ai/investigate")
async def ai_investigate(
    req: InvestigateRequest,
    user: Annotated[AuthUser, Depends(require_user)],
    x_securaiq_org: str | None = Header(default=None, alias="X-SecuraIQ-Org"),
):
    """Flagship workflow: investigate top-risk assets inside the caller's tenant."""
    oid = resolve_request_org(user, org_id=req.org_id, header_org=x_securaiq_org)
    require_perm(user, "asset.read", org_id=oid)
    require_perm(user, "vuln.read", org_id=oid)
    return investigate_top_assets(
        user.id,
        org_id=oid,
        engagement_id=req.engagement_id,
        limit=req.limit,
    )


@router.post("/risk/score")
async def risk_score_compute(req: RiskScoreRequest, user: Annotated[AuthUser, Depends(require_user)]):
    """Deterministic risk score — AI should explain, not invent."""
    _ = user
    result = compute_risk_score(
        cvss=req.cvss,
        exploitability=req.exploitability,
        exposure=req.exposure,
        asset_criticality=req.asset_criticality,
        threat_intel=req.threat_intel,
        confidence=req.confidence,
    )
    result["explanation"] = explain_risk_score(result)
    return result


@router.post("/assets")
async def assets_create(
    req: AssetCreate,
    user: Annotated[AuthUser, Depends(require_user)],
    x_securaiq_org: str | None = Header(default=None, alias="X-SecuraIQ-Org"),
):
    oid = resolve_request_org(user, header_org=x_securaiq_org)
    require_perm(user, "asset.write", org_id=oid)
    return create_asset(
        user.id,
        req.name,
        asset_type=req.asset_type,
        criticality=req.criticality,
        owner=req.owner,
        notes=req.notes,
        engagement_id=req.engagement_id,
        org_id=oid,
    )


@router.patch("/assets/{asset_id}")
async def assets_update(asset_id: str, req: AssetUpdate, user: Annotated[AuthUser, Depends(require_user)]):
    require_perm(user, "asset.write")
    out = update_asset(user.id, asset_id, req.model_dump(exclude_none=True))
    if not out:
        raise HTTPException(status_code=404, detail="Not found")
    return out


@router.delete("/assets/{asset_id}")
async def assets_delete(asset_id: str, user: Annotated[AuthUser, Depends(require_user)]):
    require_perm(user, "asset.write")
    if not delete_asset(user.id, asset_id):
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


@router.get("/risks")
async def risks_list(
    user: Annotated[AuthUser, Depends(require_user)],
    engagement_id: str | None = None,
    status: str | None = None,
    org_id: str | None = None,
    x_securaiq_org: str | None = Header(default=None, alias="X-SecuraIQ-Org"),
):
    oid = resolve_request_org(user, org_id=org_id, header_org=x_securaiq_org)
    return {"risks": list_risks(user.id, engagement_id=engagement_id, status=status, org_id=oid), "org_id": oid}


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
    org_id: str | None = None,
    x_securaiq_org: str | None = Header(default=None, alias="X-SecuraIQ-Org"),
):
    oid = resolve_request_org(user, org_id=org_id, header_org=x_securaiq_org)
    require_perm(user, "vuln.read", org_id=oid)
    return {
        "vulnerabilities": list_vulnerabilities(
            user.id, engagement_id=engagement_id, status=status, org_id=oid
        ),
        "org_id": oid,
    }


@router.get("/vulnerabilities/export")
async def vulns_export(user: Annotated[AuthUser, Depends(require_user)], engagement_id: str | None = None):
    require_perm(user, "report.export")
    return PlainTextResponse(
        export_vuln_markdown(user.id, engagement_id),
        media_type="text/markdown; charset=utf-8",
    )


@router.post("/vulnerabilities/import")
async def vulns_import(
    user: Annotated[AuthUser, Depends(require_user)],
    file: UploadFile = File(...),
    engagement_id: str | None = None,
    x_securaiq_org: str | None = Header(default=None, alias="X-SecuraIQ-Org"),
):
    oid = resolve_request_org(user, header_org=x_securaiq_org)
    require_perm(user, "vuln.write", org_id=oid)
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
    """Demo fixtures disabled — import real scanner exports via /api/vulnerabilities/import."""
    return {
        "samples": [],
        "ok": True,
        "disabled": True,
        "hint": "Lab fixtures removed. Prefer Live scan (Tools + Auth) or import Trivy/Semgrep/Gitleaks/Nessus JSON.",
    }


@router.post("/vulnerabilities/samples/{sample_id}/import")
async def vulns_sample_import(
    sample_id: str,
    user: Annotated[AuthUser, Depends(require_user)],
    engagement_id: str | None = None,
):
    raise HTTPException(
        status_code=410,
        detail="Lab sample import disabled. Use Live scan or Import with your scanner export.",
    )


@router.patch("/vulnerabilities/{vuln_id}")
async def vulns_update(vuln_id: str, req: VulnUpdate, user: Annotated[AuthUser, Depends(require_user)]):
    require_perm(user, "vuln.write")
    out = update_vulnerability(user.id, vuln_id, req.model_dump(exclude_none=True))
    if not out:
        raise HTTPException(status_code=404, detail="Not found")
    return out


class VulnTriage(BaseModel):
    owner: str = "SecOps"
    create_jira: bool = False


@router.post("/vulnerabilities/{vuln_id}/triage")
async def vulns_triage(vuln_id: str, req: VulnTriage, user: Annotated[AuthUser, Depends(require_user)]):
    """Golden path: finding → risk + remediation (+ optional Jira)."""
    require_perm(user, "vuln.triage")
    try:
        out = triage_vulnerability(user.id, vuln_id, owner=req.owner, create_ticket_hint=req.create_jira)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    jira = None
    if req.create_jira:
        try:
            from app.commercial_ext import jira_create_issue

            rem = out.get("remediation") or {}
            v = out.get("vulnerability") or {}
            summary = f"[SecuraIQ] {v.get('cve') or ''} {v.get('title') or rem.get('title')}".strip()[:255]
            jira = await jira_create_issue(
                summary=summary,
                description=(
                    f"Auto-triaged from vulnerability `{vuln_id}`.\n\n"
                    f"Severity: {v.get('severity')}\n"
                    f"Asset: {v.get('asset_name') or '—'}\n"
                    f"Risk id: {(out.get('risk') or {}).get('id')}\n"
                    f"Remediation id: {rem.get('id')}\n"
                ),
            )
            out["jira"] = jira
        except Exception as exc:
            out["jira_error"] = str(exc)
    return out


@router.post("/vulnerabilities/{vuln_id}/jira")
async def vulns_jira(vuln_id: str, user: Annotated[AuthUser, Depends(require_user)]):
    v = get_vulnerability(user.id, vuln_id)
    if not v:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        from app.commercial_ext import jira_create_issue

        summary = f"[SecuraIQ] {v.get('cve') or ''} — {v.get('title')}".strip()[:255]
        return await jira_create_issue(
            summary=summary,
            description=(
                f"Vulnerability `{vuln_id}`\n"
                f"Severity: {v.get('severity')}\n"
                f"Asset: {v.get('asset_name') or '—'}\n"
                f"Source: {v.get('source') or '—'}\n"
            ),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/gap/remediations")
async def rem_list(
    user: Annotated[AuthUser, Depends(require_user)],
    assessment_id: str | None = None,
    engagement_id: str | None = None,
    status: str | None = None,
    org_id: str | None = None,
    x_securaiq_org: str | None = Header(default=None, alias="X-SecuraIQ-Org"),
):
    oid = resolve_request_org(user, org_id=org_id, header_org=x_securaiq_org)
    return {
        "remediations": list_remediations(
            user.id,
            assessment_id=assessment_id,
            engagement_id=engagement_id,
            status=status,
            org_id=oid,
        ),
        "org_id": oid,
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
    org_id: str | None = None,
    x_securaiq_org: str | None = Header(default=None, alias="X-SecuraIQ-Org"),
):
    oid = resolve_request_org(user, org_id=org_id, header_org=x_securaiq_org)
    return {"playbooks": list_playbooks(user.id, engagement_id, org_id=oid), "org_id": oid}


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
    org_id: str | None = None,
    x_securaiq_org: str | None = Header(default=None, alias="X-SecuraIQ-Org"),
):
    oid = resolve_request_org(user, org_id=org_id, header_org=x_securaiq_org)
    return {"campaigns": list_campaigns(user.id, engagement_id, org_id=oid), "org_id": oid}


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
