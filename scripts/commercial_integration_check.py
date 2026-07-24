"""End-to-end check for SecuraIQ commercial + enterprise workflows."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080").rstrip("/")

REQUIRED_IDS = [
    "gapBtn",
    "riskBtn",
    "vulnBtn",
    "dashboardBtn",
    "intentRow",
    "globalSearch",
    "viewCommand",
    "navChat",
    "navCommand",
    "assetBtn",
    "remBtn",
    "playbookBtn",
    "campaignBtn",
    "authBtn",
    "engagementSelect",
    "gapModal",
    "gapForm",
    "riskModal",
    "riskForm",
    "vulnModal",
    "dashModal",
    "assetModal",
    "remModal",
    "playbookModal",
    "campaignModal",
    "authModal",
    "uploadBtn",
    "reportsBtn",
    "searchResults",
    "viewSoc",
    "viewIntel",
    "viewReports",
    "viewEvidence",
    "viewOrgs",
    "orgsBtn",
    "setJiraUrl",
    "toolsPalette",
    "exportMdBtn",
    "frameworksBtn",
    "viewFrameworks",
    "ccRiskHeat",
    "mcContext",
    "ccWorkQueue",
    "mcOrgName",
    "viewGraph",
    "ccRecommendedToday",
    "viewIntegrations",
    "viewBilling",
]

REQUIRED_JS_PATHS = [
    "/api/gap/run",
    "/api/dashboard",
    "/api/risks",
    "/api/vulnerabilities",
    "/api/assets",
    "/api/playbooks",
    "/api/campaigns",
    "/api/gap/remediations",
    "/api/soc",
    "/api/reports",
    "/api/search",
    "/api/intel/watch",
    "/api/engagements",
    "/api/auth/status",
    "/api/files",
    "/api/orgs",
    "/api/evidence",
    "/api/integrations/jira/issue",
    "/api/reports/executive.pdf",
    "/api/tools/run",
    "/api/graph",
    "/api/intel/kev",
    "/api/webhooks",
]


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def main() -> int:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "app.js").read_text(encoding="utf-8") + "\n" + (STATIC / "workspace.js").read_text(encoding="utf-8")
    for eid in REQUIRED_IDS:
        if f'id="{eid}"' not in html:
            fail(f"index.html missing id={eid}")
    for path in REQUIRED_JS_PATHS:
        if path not in js:
            fail(f"app.js missing {path}")
    print("OK UI wiring (gap/risk/vuln/dashboard/auth)")

    with httpx.Client(timeout=90.0) as c:
        h = c.get(f"{BASE}/api/health").json()
        if h.get("status") != "ok":
            fail(f"health {h}")
        print("OK health", h.get("backend"))

        auth = c.get(f"{BASE}/api/auth/status").json()
        if "auth_enabled" not in auth:
            fail(f"auth status {auth}")
        print("OK auth/status enabled=", auth.get("auth_enabled"))

        # Engagement
        eng = c.post(
            f"{BASE}/api/engagements",
            json={"name": "Integration engagement", "scope_notes": "authorized lab only"},
        )
        if eng.status_code != 200:
            fail(f"engagement create {eng.status_code} {eng.text}")
        eng_id = eng.json()["id"]
        print("OK engagement", eng_id[:8])

        # Chat + memory
        chat = c.post(
            f"{BASE}/api/chats",
            json={"title": "Integration chat", "mode": "ciso", "engagement_id": eng_id},
        )
        if chat.status_code != 200:
            fail(f"chat create {chat.status_code}")
        chat_id = chat.json()["id"]
        c.post(
            f"{BASE}/api/chats/{chat_id}/messages",
            json={"role": "user", "content": "Integration check message"},
        )
        c.post(
            f"{BASE}/api/engagements/{eng_id}/memories",
            json={"key": "scope", "value": "10.10.10.0/24 lab"},
        )
        exp = c.get(f"{BASE}/api/chats/{chat_id}/export")
        if exp.status_code != 200 or "SecuraIQ" not in exp.text:
            fail(f"chat export {exp.status_code}")
        print("OK chats/memory/export")

        # File upload
        up = c.post(
            f"{BASE}/api/files",
            params={"engagement_id": eng_id, "ingest": "false"},
            files={"file": ("policy.txt", b"Information security policy MFA EDR backup IR plan", "text/plain")},
        )
        if up.status_code != 200:
            fail(f"upload {up.status_code} {up.text}")
        file_id = up.json()["id"]
        print("OK file upload", file_id[:8])

        # Frameworks + gap with file evidence
        fws = c.get(f"{BASE}/api/frameworks").json().get("frameworks") or []
        if len(fws) < 3:
            fail(f"frameworks {fws}")
        gap = c.post(
            f"{BASE}/api/gap/run",
            json={
                "framework_id": "iso27001",
                "title": "Integration gap",
                "engagement_id": eng_id,
                "evidence": "information security policy MFA authentication EDR endpoint vulnerability patch logging SIEM backup restore incident response awareness training",
                "file_ids": [file_id],
            },
        )
        if gap.status_code != 200:
            fail(f"gap run {gap.status_code} {gap.text}")
        g = gap.json()
        if g.get("compliance_percent") is None or not g.get("id"):
            fail(f"gap payload {g}")
        if int(g.get("remediations_created") or 0) < 1 and (g.get("counts") or {}).get("missing", 0) > 0:
            fail(f"expected remediations for gaps: {g.get('remediations_created')}")
        aid = g["id"]
        rem = c.get(f"{BASE}/api/gap/remediations", params={"assessment_id": aid}).json()
        if not rem.get("remediations"):
            # may be empty if fully compliant — still OK if remediations_created == 0
            if g.get("remediations_created", 0) > 0:
                fail("remediations list empty after seed")
        if rem.get("remediations"):
            rid = rem["remediations"][0]["id"]
            patched = c.patch(
                f"{BASE}/api/gap/remediations/{rid}",
                json={"status": "done", "owner": "SecOps"},
            )
            if patched.status_code != 200 or patched.json().get("status") != "done":
                fail(f"remediation patch {patched.status_code} {patched.text}")
        gexp = c.get(f"{BASE}/api/gap/assessments/{aid}/export")
        if gexp.status_code != 200 or "Gap Analysis" not in gexp.text:
            fail(f"gap export {gexp.status_code}")
        print(
            "OK gap",
            g.get("compliance_percent"),
            "% remediations=",
            g.get("remediations_created"),
        )

        # Risk register
        risk = c.post(
            f"{BASE}/api/risks",
            json={
                "threat": "Ransomware",
                "vulnerability": "No offline backups",
                "asset_name": "File server",
                "impact": 5,
                "likelihood": 3,
                "owner": "IT",
                "mitigation": "Immutable backups",
                "engagement_id": eng_id,
            },
        )
        if risk.status_code != 200 or risk.json().get("risk_score") != 15:
            fail(f"risk create {risk.status_code} {risk.text}")
        risk_id = risk.json()["id"]
        rp = c.patch(f"{BASE}/api/risks/{risk_id}", json={"status": "mitigated"})
        if rp.status_code != 200 or rp.json().get("status") != "mitigated":
            fail(f"risk patch {rp.text}")
        rexp = c.get(f"{BASE}/api/risks/export")
        if rexp.status_code != 200 or "Risk Assessment" not in rexp.text:
            fail(f"risk export {rexp.status_code}")
        print("OK risks score=15 mitigated + export")

        # Assets
        asset = c.post(
            f"{BASE}/api/assets",
            json={"name": "jumpbox", "asset_type": "server", "engagement_id": eng_id},
        )
        if asset.status_code != 200:
            fail(f"asset {asset.status_code} {asset.text}")
        print("OK assets")

        # Vuln import
        imp = c.post(
            f"{BASE}/api/vulnerabilities/import",
            params={"engagement_id": eng_id},
            files={
                "file": (
                    "scan.csv",
                    b"title,cve,severity,asset\nOpenSSH,CVE-2023-38408,high,jumpbox\nXSS,CVE-2024-0001,medium,portal\n",
                    "text/csv",
                )
            },
        )
        if imp.status_code != 200 or imp.json().get("imported") != 2:
            fail(f"vuln import {imp.status_code} {imp.text}")
        vulns = c.get(f"{BASE}/api/vulnerabilities").json().get("vulnerabilities") or []
        if not vulns:
            fail("no vulnerabilities listed")
        vid = vulns[0]["id"]
        vp = c.patch(f"{BASE}/api/vulnerabilities/{vid}", json={"status": "closed", "owner": "AppSec"})
        if vp.status_code != 200 or vp.json().get("status") != "closed":
            fail(f"vuln patch {vp.text}")
        vexp = c.get(f"{BASE}/api/vulnerabilities/export")
        if vexp.status_code != 200 or "Vulnerability Summary" not in vexp.text:
            fail(f"vuln export {vexp.status_code}")
        print("OK vulns import=2 + close + export")

        # Tools + awareness
        tools = c.get(f"{BASE}/api/tools").json()
        if tools.get("available_count", 0) < 1:
            fail(f"tools {tools}")
        aw = tools.get("auto_awareness") or []
        if "phishing_url" not in aw or "email_auth" not in aw:
            fail(f"auto_awareness missing: {aw}")
        print("OK tools", tools.get("available_count"), "awareness=", ",".join(aw))

        # Router
        route = c.post(f"{BASE}/api/router", json={"message": "ISO gap analysis", "mode": "ciso"})
        if route.status_code != 200:
            fail(f"router {route.status_code}")
        print("OK router")

        # Dashboard live
        dash = c.get(f"{BASE}/api/dashboard").json()
        for key in (
            "compliance_score",
            "risks_total",
            "vulnerabilities_total",
            "remediations_total",
            "assets_total",
            "findings",
        ):
            if key not in dash:
                fail(f"dashboard missing {key}: {dash}")
        print(
            "OK dashboard",
            f"compliance={dash.get('compliance_score')}",
            f"risks={dash.get('risks_total')}",
            f"vulns={dash.get('vulnerabilities_total')}",
            f"assets={dash.get('assets_total')}",
        )

        # Modes include awareness + ciso
        modes = c.get(f"{BASE}/api/modes").json().get("modes") or []
        for m in ("awareness", "ciso", "assess", "purple", "threat_hunt", "ir", "cloud", "appsec", "tabletop"):
            if m not in modes:
                fail(f"mode missing {m}")
        print("OK modes include purple/IR/cloud/appsec/tabletop set")

        # Audit
        audit = c.get(f"{BASE}/api/audit").json()
        if not audit.get("events"):
            fail("audit empty")
        print("OK audit events=", len(audit["events"]))

        # Short awareness chat with tools (stream markers)
        with c.stream(
            "POST",
            f"{BASE}/api/chat",
            json={
                "message": "Review this lure URL for awareness: https://secure-login.paypal-support.example/signin",
                "history": [],
                "mode": "awareness",
                "use_rag": False,
                "use_web_search": False,
                "use_net_assess": False,
                "use_local_tools": True,
            },
        ) as resp:
            if resp.status_code != 200:
                fail(f"awareness chat {resp.status_code}")
            buf = ""
            for chunk in resp.iter_text():
                buf += chunk
                if len(buf) > 1500:
                    break
        if "[[live:tools]]" not in buf and "[[live:start]]" not in buf:
            fail(f"awareness chat missing live markers: {buf[:200]!r}")
        print("OK awareness chat live markers")

        # Organizations + evidence + PDF + Jira gate
        org = c.post(f"{BASE}/api/orgs", json={"name": "Integration Org"})
        if org.status_code != 200:
            fail(f"org create {org.status_code} {org.text}")
        org_id = org.json().get("id")
        orgs = c.get(f"{BASE}/api/orgs").json().get("organizations") or []
        if not any(o.get("id") == org_id for o in orgs):
            fail("org not listed")
        print("OK orgs", org_id[:8] if org_id else "?")

        ev = c.post(
            f"{BASE}/api/evidence",
            json={"file_id": file_id, "control_id": "A.5.1", "notes": "policy evidence"},
        )
        if ev.status_code != 200:
            fail(f"evidence link {ev.status_code} {ev.text}")
        evl = c.get(f"{BASE}/api/evidence").json().get("evidence") or []
        if not evl:
            fail("evidence list empty")
        print("OK evidence links", len(evl))

        pdf = c.get(f"{BASE}/api/reports/executive.pdf")
        if pdf.status_code != 200 or not pdf.content.startswith(b"%PDF"):
            fail(f"executive pdf {pdf.status_code} prefix={pdf.content[:8]!r}")
        catalog = c.get(f"{BASE}/api/reports").json().get("reports") or []
        if not any((r.get("kind") == "pdf") for r in catalog):
            fail("reports catalog missing pdf entries")
        print("OK pdf + catalog")

        jira = c.post(
            f"{BASE}/api/integrations/jira/issue",
            json={"summary": "SecuraIQ integration probe"},
        )
        if jira.status_code != 400:
            fail(f"expected jira 400 when unconfigured, got {jira.status_code} {jira.text}")
        print("OK jira unconfigured gate")

        # Platform: graph, scanners, office exports, webhooks
        g = c.get(f"{BASE}/api/graph")
        if g.status_code != 200 or "nodes" not in g.json():
            fail(f"graph {g.status_code} {g.text[:200]}")
        trivy = {
            "Results": [
                {
                    "Target": "lab-app",
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2024-0001",
                            "Title": "Sample",
                            "Severity": "HIGH",
                            "PkgName": "openssl",
                        }
                    ],
                }
            ]
        }
        timp = c.post(
            f"{BASE}/api/vulnerabilities/import",
            params={"engagement_id": eng_id},
            files={"file": ("trivy.json", json.dumps(trivy).encode(), "application/json")},
        )
        if timp.status_code != 200 or timp.json().get("adapter") != "trivy":
            fail(f"trivy import {timp.status_code} {timp.text[:300]}")
        xlsx = c.get(f"{BASE}/api/reports/risks.xlsx")
        if xlsx.status_code != 200 or len(xlsx.content) < 50:
            fail(f"risks xlsx {xlsx.status_code}")
        docx = c.get(f"{BASE}/api/reports/executive.docx")
        if docx.status_code != 200 or len(docx.content) < 50:
            fail(f"exec docx {docx.status_code}")
        wh = c.post(
            f"{BASE}/api/webhooks",
            json={"name": "test-hook", "url": "http://127.0.0.1:9/nope", "events": ["*"]},
        )
        if wh.status_code != 200:
            fail(f"webhook create {wh.status_code} {wh.text}")
        fws = c.get(f"{BASE}/api/frameworks").json().get("frameworks") or []
        ids = {f.get("id") for f in fws}
        if not {"soc2", "pci_dss", "owasp_asvs"} <= ids:
            fail(f"frameworks missing expanded set: {ids}")
        print("OK platform graph + trivy + office + webhooks + frameworks")

    print("\nALL COMMERCIAL + ENTERPRISE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
