"""Live functional check: APIs + CRUD + static button wiring."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080").rstrip("/")

GETS = [
    "/api/health",
    "/api/dashboard",
    "/api/soc",
    "/api/assets",
    "/api/risks",
    "/api/vulnerabilities",
    "/api/playbooks",
    "/api/campaigns",
    "/api/gap/remediations",
    "/api/gap/assessments",
    "/api/gap/evidence-queue",
    "/api/frameworks",
    "/api/files",
    "/api/evidence",
    "/api/orgs",
    "/api/reports",
    "/api/webhooks",
    "/api/graph",
    "/api/jobs",
    "/api/billing/plans",
    "/api/auth/status",
    "/api/xdr/status",
    "/api/wazuh/status",
    "/api/thehive/status",
    "/api/cloud/status",
    "/api/openaudit/status",
    "/api/hardeningkitty/status",
    "/api/integrations/catalog",
    "/api/tools",
    "/api/notifications",
    "/api/settings",
    "/api/intel/watch",
    "/api/intel/kev",
    "/api/intel/free/catalog",
    "/api/intel/threat-detection",
]

CRITICAL_IDS = [
    "send",
    "navCommand",
    "navChat",
    "newChatBtn",
    "gapBtn",
    "assetBtn",
    "vulnBtn",
    "riskBtn",
    "settingsBtn",
    "authBtn",
    "input",
    "composer",
    "liveTicker",
    "frameworksBtn",
    "frameworksRunGap",
    "hkAuditBtn",
]


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def main() -> int:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "app.js").read_text(encoding="utf-8") + "\n" + (STATIC / "workspace.js").read_text(encoding="utf-8")
    for eid in CRITICAL_IDS:
        if f'id="{eid}"' not in html:
            fail(f"missing html id={eid}")
        if eid not in js:
            fail(f"js never mentions {eid}")
    print("OK critical UI ids in html+js")

    ids = set(re.findall(r'id="([^"]+Btn)"', html))
    missing = sorted(i for i in ids if i not in js and i not in {"topHelpBtn"})
    if missing:
        print("WARN buttons not referenced in JS:", ", ".join(missing[:20]))
    else:
        print("OK all *Btn ids referenced in JS (except Help)")

    with httpx.Client(timeout=60.0) as c:
        for path in GETS:
            r = c.get(f"{BASE}{path}")
            if r.status_code != 200:
                fail(f"GET {path} -> {r.status_code} {r.text[:160]}")
        print(f"OK {len(GETS)} GET endpoints")

        asset = c.post(f"{BASE}/api/assets", json={"name": "lab-host", "asset_type": "server", "criticality": "high"})
        if asset.status_code != 200:
            fail(f"asset create {asset.status_code} {asset.text}")
        aid = asset.json()["id"]
        c.delete(f"{BASE}/api/assets/{aid}")
        print("OK assets CRUD")

        risk = c.post(
            f"{BASE}/api/risks",
            json={"threat": "Phish", "vulnerability": "User", "impact": 3, "likelihood": 2},
        )
        if risk.status_code != 200:
            fail(f"risk create {risk.status_code} {risk.text}")
        rid = risk.json()["id"]
        c.patch(f"{BASE}/api/risks/{rid}", json={"status": "mitigated"})
        c.delete(f"{BASE}/api/risks/{rid}")
        print("OK risks CRUD")

        pb = c.post(
            f"{BASE}/api/playbooks",
            json={"title": "Lab IR", "category": "ir", "severity": "high", "steps": "1. contain"},
        )
        if pb.status_code != 200:
            fail(f"playbook {pb.status_code} {pb.text}")
        pid = pb.json()["id"]
        c.delete(f"{BASE}/api/playbooks/{pid}")
        print("OK playbooks CRUD")

        camp = c.post(
            f"{BASE}/api/campaigns",
            json={"name": "Lab awareness", "status": "planned", "audience": "staff"},
        )
        if camp.status_code != 200:
            fail(f"campaign {camp.status_code} {camp.text}")
        cid = camp.json()["id"]
        c.patch(f"{BASE}/api/campaigns/{cid}", json={"status": "completed"})
        c.delete(f"{BASE}/api/campaigns/{cid}")
        print("OK campaigns CRUD")

        inc = c.post(f"{BASE}/api/incidents", json={"title": "Lab incident", "severity": "medium"})
        if inc.status_code != 200:
            fail(f"incident {inc.status_code} {inc.text}")
        iid = inc.json()["id"]
        c.patch(f"{BASE}/api/incidents/{iid}", json={"status": "closed"})
        c.delete(f"{BASE}/api/incidents/{iid}")
        print("OK incidents CRUD")

        imp = c.post(
            f"{BASE}/api/cloud/import",
            json={"vendor": "cloud_import", "findings": [{"id": "fn-lab", "title": "Lab finding", "severity": "low"}]},
        )
        if imp.status_code != 200:
            fail(f"cloud import {imp.status_code} {imp.text}")
        print("OK cloud import")

        job = c.post(f"{BASE}/api/jobs", json={"kind": "kev_sync", "engine": "local", "payload": {}})
        if job.status_code != 200:
            fail(f"job enqueue {job.status_code} {job.text}")
        print("OK job enqueue", job.json().get("id", "")[:8])

        cat = c.get(f"{BASE}/api/integrations/catalog").json()
        slack = None
        for g in cat.get("groups") or []:
            for it in g.get("items") or []:
                if it.get("id") == "slack":
                    slack = it.get("ui_action") or {}
        if not slack or slack.get("kind") != "settings":
            fail(f"slack catalog action {slack}")
        print("OK catalog slack -> settings")

        st = c.get(f"{BASE}/api/settings").json()
        for key in ("slack_webhook_url_set", "servicenow_instance_url", "sophos_client_id", "smtp_host"):
            if key not in st:
                fail(f"settings missing {key}")
        print("OK settings keys for comms/xdr")

        # Built-in compliance / intel integration
        fws = c.get(f"{BASE}/api/frameworks").json().get("frameworks") or []
        if len(fws) < 10:
            fail(f"frameworks too few: {len(fws)}")
        for need in ("iso27001", "nist_csf", "cis_controls", "owasp_asvs", "nist_800_53"):
            if not any(f.get("id") == need for f in fws):
                fail(f"missing framework {need}")
        detail = c.get(f"{BASE}/api/frameworks/iso27001").json()
        if len(detail.get("controls") or []) < 90:
            fail(f"iso27001 controls {len(detail.get('controls') or [])}")
        print("OK frameworks catalog", len(fws), "total controls", sum(int(f.get("control_count") or 0) for f in fws))

        gap = c.post(
            f"{BASE}/api/gap/run",
            json={
                "framework_id": "owasp_top10",
                "title": "Functional gap check",
                "evidence": "access control MFA encryption TLS logging monitoring SBOM dependency scan",
            },
        )
        if gap.status_code != 200:
            fail(f"gap run {gap.status_code} {gap.text[:200]}")
        gj = gap.json()
        if gj.get("compliance_percent") is None or not gj.get("id"):
            fail(f"gap payload {gj}")
        print("OK gap run", gj.get("framework_name"), gj.get("compliance_percent"), "%")

        samp = c.get(f"{BASE}/api/vulnerabilities/samples").json()
        if not samp.get("disabled"):
            fail(f"lab samples should be disabled: {samp}")
        print("OK lab samples disabled")

        atd = c.get(f"{BASE}/api/intel/threat-detection", params={"q": "sigma", "limit": 3})
        if atd.status_code != 200:
            fail(f"threat-detection {atd.status_code}")
        atj = atd.json()
        if not atj.get("ok") and not atj.get("total"):
            fail(f"threat-detection payload {atj}")
        print("OK threat-detection total=", atj.get("total"))

        cat = c.get(f"{BASE}/api/integrations/catalog").json()
        hk_action = None
        for g in cat.get("groups") or []:
            for it in g.get("items") or []:
                if it.get("id") == "hardeningkitty":
                    hk_action = it.get("ui_action") or {}
                if it.get("id") == "iso27001":
                    ua = it.get("ui_action") or {}
                    if ua.get("target") != "frameworks":
                        fail(f"iso27001 ui_action {ua}")
        if not hk_action or hk_action.get("target") != "frameworks":
            fail(f"hardeningkitty ui_action {hk_action}")
        print("OK catalog -> frameworks for compliance/hardening")

    print("ALL FUNCTIONAL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
