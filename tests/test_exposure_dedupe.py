"""Private-lab Windows port down-rank + cross-tool port dedupe."""

from __future__ import annotations

import importlib

from app.exposure import network_scope, risky_port_finding, severity_for_risky_port


def test_private_windows_ports_are_info():
    assert network_scope("192.168.56.1") == "private"
    assert severity_for_risky_port(445, "private") == "info"
    assert severity_for_risky_port(135, "private") == "info"
    assert severity_for_risky_port(139, "private") == "info"
    # Public stays serious
    assert severity_for_risky_port(445, "public") == "high"


def test_reclassify_legacy_high_smb(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("WORKSPACE_ZERO_START", "false")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("DEPLOYMENT_MODE", "lab")
    monkeypatch.setenv("DATABASE_URL", "")
    import app.config as config_mod
    import app.db as db_mod

    importlib.reload(config_mod)
    db_mod.reset_conn_for_tests()
    importlib.reload(db_mod)

    from app.auth import register_user
    from app.enterprise import create_vulnerability, get_vulnerability
    from app.exposure import reclassify_stored_risky_ports
    from app.tenancy import ensure_tenant_schema

    ensure_tenant_schema()
    user = register_user("smb_fix", "password123", role="user")
    v = create_vulnerability(
        user.id,
        {
            "title": "Hardening gap: Exposed risky port 445/tcp — SMB (frequent ransomware/lateral-movement vector when exposed)",
            "severity": "high",
            "asset_name": "192.168.56.1",
            "source": "hardening_baseline",
            "raw": {"port": 445},
        },
        emit_realtime=False,
    )
    out = reclassify_stored_risky_ports(user.id)
    assert out["updated"] >= 1
    fixed = get_vulnerability(user.id, v["id"])
    assert fixed["severity"] == "info"
    assert "Windows LAN" in fixed["title"] or "private" in fixed["title"].lower()


def test_risky_port_finding_title_for_lab_gateway():
    item = risky_port_finding(445, target="192.168.56.1", source="ports:port-445", ip="192.168.56.1")
    assert item["severity"] == "info"
    assert "Windows LAN" in item["title"] or "private" in item["title"].lower()


def test_cross_tool_dedupe_same_ports(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("WORKSPACE_ZERO_START", "false")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("DEPLOYMENT_MODE", "lab")
    monkeypatch.setenv("DATABASE_URL", "")
    import app.config as config_mod
    import app.db as db_mod

    importlib.reload(config_mod)
    db_mod.reset_conn_for_tests()
    importlib.reload(db_mod)

    from app.auth import register_user
    from app.enterprise import list_vulnerabilities
    from app.tools.runner import persist_tool_findings_to_vulns

    user = register_user("dedupe_u", "password123", role="user")
    payload = {
        "target": "192.168.56.1",
        "ip": "192.168.56.1",
        "requested": ["ports", "hardening_baseline", "openvas"],
        "runs": [
            {"ok": True, "tool": "ports", "open_ports": [135, 139, 445], "output": "Open: [135, 139, 445]"},
            {
                "ok": True,
                "tool": "hardening_baseline",
                "output": (
                    "[FAIL] LAN-reachable port 135/tcp — MSRPC\n"
                    "[FAIL] LAN-reachable port 139/tcp — NetBIOS\n"
                    "[FAIL] LAN-reachable port 445/tcp — SMB\n"
                ),
            },
            {
                "ok": True,
                "tool": "openvas",
                "output": (
                    "[FAIL] LAN-reachable service on port 135/tcp — MSRPC\n"
                    "[FAIL] LAN-reachable service on port 139/tcp — NetBIOS\n"
                    "[FAIL] LAN-reachable service on port 445/tcp — SMB\n"
                ),
                "cve_matches": [],
            },
        ],
    }
    result = persist_tool_findings_to_vulns(user.id, payload)
    vulns = list_vulnerabilities(user.id)
    # One finding per port, not 9
    port_findings = [v for v in vulns if (v.get("raw") or {}).get("port") in {135, 139, 445}
                     or "port 135" in (v.get("title") or "").lower()
                     or "port 139" in (v.get("title") or "").lower()
                     or "port 445" in (v.get("title") or "").lower()
                     or "Windows LAN" in (v.get("title") or "")]
    assert result.get("created", result.get("count", len(vulns))) >= 1
    assert len(port_findings) == 3
    assert all((v.get("severity") or "").lower() == "info" for v in port_findings)
