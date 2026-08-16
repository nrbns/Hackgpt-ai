"""SecuraIQ SIEM API — branding + offline behavior (no live manager required)."""

from __future__ import annotations

from app.wazuh_api import normalize_siem_alert


def test_normalize_siem_alert_branding():
    item = normalize_siem_alert(
        {
            "rule": {"id": "5501", "level": 10, "description": "Login failure"},
            "agent": {"name": "lab-host", "ip": "10.0.0.5"},
            "full_log": "sshd: failed",
        }
    )
    assert item["vendor"] == "wazuh"
    assert item["kind"] == "siem_alert"
    assert item["severity"] == "high"
    assert item["host"] == "lab-host"
    assert item["title"] == "Login failure"
    assert item["external_id"].startswith("siem:")


def test_normalize_fallback_title():
    item = normalize_siem_alert({"rule": {"id": "99", "level": 3}})
    assert "SIEM rule" in item["title"]
    assert item["severity"] == "low"


def test_overview_unconfigured(tmp_data_dir, monkeypatch):
    monkeypatch.setenv("WAZUH_BASE_URL", "")
    monkeypatch.setenv("WAZUH_USER", "")
    monkeypatch.setenv("WAZUH_PASSWORD", "")
    # Re-import settings after env — use connector helper directly
    from app.connectors import wazuh as wz

    assert wz.is_configured() is False


def test_siem_routes_mounted():
    from fastapi.routing import APIRoute

    from app.wazuh_api import router

    route_paths = {r.path for r in router.routes if isinstance(r, APIRoute)}
    for needed in ("/status", "/overview", "/sync", "/agents", "/alerts", "/groups", "/modules", "/webhook"):
        assert needed in route_paths, f"missing {needed} on SIEM router: {sorted(route_paths)}"
