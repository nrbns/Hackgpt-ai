#!/usr/bin/env python3
"""Full end-to-end smoke: static UI + enterprise APIs + chat."""
from __future__ import annotations

import sys
from pathlib import Path

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080").rstrip("/")
ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
fails: list[str] = []


def fail(msg: str) -> None:
    fails.append(msg)
    print(f"FAIL: {msg}")


def ok(msg: str) -> None:
    print(f"OK {msg}")


def main() -> int:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    css = (STATIC / "style.css").read_text(encoding="utf-8")

    required_ids = [
        "navCommand",
        "navChat",
        "viewCommand",
        "viewChat",
        "ccScore",
        "ccAskAi",
        "globalSearch",
        "intentRow",
        "composerWrap",
        "gapBtn",
        "riskBtn",
        "vulnBtn",
        "assetBtn",
        "remBtn",
        "playbookBtn",
        "campaignBtn",
        "dashboardBtn",
        "mode",
        "send",
        "input",
        "attachBtn",
        "gapModal",
        "riskModal",
        "vulnModal",
        "assetModal",
        "remModal",
        "playbookModal",
        "campaignModal",
        "dashModal",
        "newChatBtn",
        "engagementSelect",
    ]
    for eid in required_ids:
        if f'id="{eid}"' not in html:
            fail(f"missing id={eid}")
    else:
        ok(f"html ids ({len(required_ids)})")

    for needle in [
        "showView",
        "loadCommandCenter",
        "wireCommandCenterUi",
        "openGap",
        "openRisk",
        "openVuln",
        "openAsset",
        "openRem",
        "openPlaybook",
        "openCampaign",
        "sendMessage",
        'on(gapBtn, "click", openGap)',
        'on(assetBtn, "click", openAsset)',
        'on(playbookBtn, "click", openPlaybook)',
        'on(campaignBtn, "click", openCampaign)',
    ]:
        if needle not in js:
            fail(f"app.js missing {needle}")
    else:
        ok("app.js wiring")

    for needle in ["cc-kpi", "side-nav", "intent-chip", "workspace-view", "CC_LAYOUT_FIX_V30"]:
        if needle not in css:
            fail(f"style.css missing {needle}")
    else:
        ok("style.css command center")

    if "style.css?v=30" not in html or "app.js?v=30" not in html:
        # accept current cache bust 30+
        if "style.css?v=" not in html or "app.js?v=" not in html:
            fail("cache bust missing")
        else:
            ok("cache bust present")
    else:
        ok("cache v=30")

    with httpx.Client(timeout=120.0) as c:
        # Health
        h = c.get(f"{BASE}/api/health").json()
        if h.get("status") != "ok":
            fail(f"health {h}")
        else:
            ok(f"health backend={h.get('backend')} ready={h.get('backend_ready')}")

        # Modes
        modes = c.get(f"{BASE}/api/modes").json()
        mode_list = modes.get("modes") or []
        needed_modes = [
            "default",
            "purple",
            "threat_hunt",
            "ir",
            "cloud",
            "appsec",
            "tabletop",
            "awareness",
            "ciso",
        ]
        for m in needed_modes:
            if m not in mode_list:
                fail(f"mode missing {m}")
        qp = modes.get("quick_prompts") or {}
        for m in needed_modes:
            if m not in qp or not qp[m]:
                fail(f"quick_prompts missing {m}")
        ok(f"modes={len(mode_list)} quick_prompts ok")

        # Static served
        page = c.get(f"{BASE}/").text
        if "viewCommand" not in page:
            fail("index not served")
        js_body = c.get(f"{BASE}/app.js?v=30").text
        if "wireCommandCenterUi" not in js_body:
            fail("app.js not served")
        ok("static served")

        # Auth status
        auth = c.get(f"{BASE}/api/auth/status").json()
        ok(f"auth_enabled={auth.get('auth_enabled')}")

        # Engagement
        eng = c.post(
            f"{BASE}/api/engagements",
            json={"name": "E2E Workspace", "scope_notes": "lab"},
        )
        if eng.status_code >= 400:
            fail(f"engagement create {eng.status_code} {eng.text[:200]}")
            eng_id = None
        else:
            eng_id = eng.json().get("id")
            ok(f"engagement {eng_id}")

        # Assets
        a = c.post(
            f"{BASE}/api/assets",
            json={"name": "E2E Web", "asset_type": "app", "criticality": "high", "engagement_id": eng_id},
        )
        if a.status_code >= 400:
            fail(f"asset create {a.status_code} {a.text[:200]}")
        else:
            aid = a.json().get("id")
            assets = c.get(f"{BASE}/api/assets").json().get("assets") or []
            if not any(x.get("id") == aid for x in assets):
                fail("asset not listed")
            else:
                ok(f"assets create/list id={aid}")

        # Risks
        r = c.post(
            f"{BASE}/api/risks",
            json={
                "threat": "E2E ransomware",
                "vulnerability": "No MFA",
                "asset_name": "E2E Web",
                "impact": 4,
                "likelihood": 3,
                "engagement_id": eng_id,
            },
        )
        if r.status_code >= 400:
            fail(f"risk create {r.status_code}")
        else:
            rid = r.json().get("id")
            c.patch(f"{BASE}/api/risks/{rid}", json={"status": "mitigated"})
            ok(f"risks create/patch score={r.json().get('risk_score')}")

        # Vuln import CSV
        csv_body = "severity,cve,title,asset\ncritical,CVE-2024-0001,E2E RCE,E2E Web\nhigh,CVE-2024-0002,E2E XSS,E2E Web\n"
        vi = c.post(
            f"{BASE}/api/vulnerabilities/import",
            params={"engagement_id": eng_id} if eng_id else None,
            files={"file": ("e2e.csv", csv_body.encode(), "text/csv")},
        )
        if vi.status_code >= 400:
            fail(f"vuln import {vi.status_code} {vi.text[:200]}")
        else:
            ok(f"vuln import={vi.json().get('imported')}")

        # Gap analysis
        gap = c.post(
            f"{BASE}/api/gap/run",
            json={
                "framework_id": "iso27001",
                "title": "E2E gap",
                "evidence": (
                    "information security policy MFA authentication EDR endpoint "
                    "vulnerability patch logging SIEM backup restore incident response "
                    "awareness training access control asset inventory"
                ),
                "engagement_id": eng_id,
            },
        )
        if gap.status_code >= 400:
            fail(f"gap {gap.status_code} {gap.text[:200]}")
        else:
            g = gap.json()
            ok(f"gap {g.get('compliance_percent')}% remediations={g.get('remediations_created')}")

        # Remediations list
        rems = c.get(f"{BASE}/api/gap/remediations").json().get("remediations") or []
        ok(f"remediations listed={len(rems)}")
        if rems:
            rem_id = rems[0]["id"]
            patch = c.patch(f"{BASE}/api/gap/remediations/{rem_id}", json={"status": "done"})
            if patch.status_code >= 400:
                fail(f"rem patch {patch.status_code}")
            else:
                ok("remediation patch done")

        # Playbooks
        pbs = c.get(f"{BASE}/api/playbooks").json().get("playbooks") or []
        if len(pbs) < 1:
            fail("playbooks empty (defaults should seed)")
        else:
            ok(f"playbooks={len(pbs)}")
        pb = c.post(
            f"{BASE}/api/playbooks",
            json={"title": "E2E playbook", "category": "ir", "steps": "1. Contain\n2. Recover"},
        )
        if pb.status_code >= 400:
            fail(f"playbook create {pb.status_code}")
        else:
            ok(f"playbook create {pb.json().get('id')}")

        # Campaigns
        camp = c.post(
            f"{BASE}/api/campaigns",
            json={
                "name": "E2E phish sim",
                "audience": "Finance",
                "sent_count": 50,
                "click_count": 5,
                "report_count": 20,
            },
        )
        if camp.status_code >= 400:
            fail(f"campaign create {camp.status_code} {camp.text[:200]}")
        else:
            cid = camp.json().get("id")
            c.patch(f"{BASE}/api/campaigns/{cid}", json={"status": "running"})
            ok(f"campaign create/patch {cid}")

        # Dashboard
        dash = c.get(f"{BASE}/api/dashboard").json()
        for key in (
            "compliance_score",
            "risks_open",
            "vulnerabilities_open",
            "assets_total",
            "playbooks_total",
            "campaigns_total",
            "recommendations",
        ):
            if key not in dash:
                fail(f"dashboard missing {key}")
        ok(
            f"dashboard compliance={dash.get('compliance_score')} "
            f"assets={dash.get('assets_total')} playbooks={dash.get('playbooks_total')}"
        )

        # Tools
        tools = c.get(f"{BASE}/api/tools").json()
        ok(f"tools available={tools.get('available_count')}")

        # Router
        route = c.post(f"{BASE}/api/router", json={"message": "board report", "mode": "ciso"}).json()
        ok(f"router {route.get('recommended_backend')}")

        # Chat stream
        with c.stream(
            "POST",
            f"{BASE}/api/chat",
            json={
                "message": "Reply with exactly: ALL_OK",
                "history": [],
                "mode": "default",
                "use_rag": False,
                "use_web_search": False,
                "use_net_assess": False,
                "use_local_tools": False,
            },
        ) as resp:
            if resp.status_code >= 400:
                fail(f"chat http {resp.status_code}")
                buf = ""
            else:
                buf = ""
                for chunk in resp.iter_text():
                    buf += chunk
                    if len(buf) > 800:
                        break
        if "[[live:" not in buf:
            fail(f"chat missing live markers: {buf[:180]!r}")
        else:
            ok(f"chat stream live markers (ALL_OK={'ALL_OK' in buf})")

        # Awareness chat tools path (light)
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
            buf2 = ""
            for chunk in resp.iter_text():
                buf2 += chunk
                if len(buf2) > 900:
                    break
        if "[[live:" not in buf2:
            fail(f"awareness chat missing live: {buf2[:180]!r}")
        else:
            ok("awareness chat live markers")

    if fails:
        print(f"\n{len(fails)} FAILURES")
        return 1
    print("\nALL SYSTEMS GO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
