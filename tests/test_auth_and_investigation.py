"""Auth session expiry, API key isolation, cookies, risk score, AI investigation."""

from __future__ import annotations

import importlib
import time

import pytest


def _reload(monkeypatch, data_dir):
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("WORKSPACE_ZERO_START", "false")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("DEPLOYMENT_MODE", "lab")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("SESSION_DAYS", "14")
    import app.config as config_mod
    import app.db as db_mod

    importlib.reload(config_mod)
    db_mod.reset_conn_for_tests()
    importlib.reload(db_mod)
    return config_mod, db_mod


def test_session_expires(tmp_path, monkeypatch):
    data_dir = tmp_path / "auth"
    data_dir.mkdir()
    _reload(monkeypatch, data_dir)
    from app.auth import hash_token, login, register_user, resolve_user
    from app.db import get_conn, now

    register_user("sess_user", "password123", role="user")
    result = login("sess_user", "password123")
    assert not isinstance(result, dict)
    _user, token = result
    # Force expiry in the past
    get_conn().execute(
        "UPDATE sessions SET expires_at = ? WHERE token = ?",
        (now() - 10, hash_token(token)),
    )
    get_conn().commit()
    assert resolve_user(f"Bearer {token}") is None


def test_api_key_isolation(tmp_path, monkeypatch):
    data_dir = tmp_path / "keys"
    data_dir.mkdir()
    _reload(monkeypatch, data_dir)
    from app.auth import create_api_key, list_api_keys, register_user, resolve_user

    a = register_user("key_a", "password123", role="user")
    b = register_user("key_b", "password123", role="user")
    raw_a, meta_a = create_api_key(a.id, "a-key")
    raw_b, _meta_b = create_api_key(b.id, "b-key")

    assert all(k["id"] != meta_a["id"] for k in list_api_keys(b.id))
    assert all(k["name"] != "a-key" for k in list_api_keys(b.id))
    ua = resolve_user(None, raw_a)
    ub = resolve_user(None, raw_b)
    assert ua and ua.id == a.id
    assert ub and ub.id == b.id
    assert ua.id != ub.id


def test_cookie_session_resolves(tmp_path, monkeypatch):
    data_dir = tmp_path / "cookie"
    data_dir.mkdir()
    _reload(monkeypatch, data_dir)
    from app.auth import login, register_user, resolve_user

    register_user("cookie_u", "password123", role="user")
    _u, token = login("cookie_u", "password123")
    assert resolve_user(None, None, token) is not None
    assert resolve_user(None, None, "bogus") is None


def test_deterministic_risk_score():
    from app.services.risk import compute_risk_score, explain_risk_score

    a = compute_risk_score(cvss=9.8, exploitability=0.9, exposure=0.9, asset_criticality="critical")
    b = compute_risk_score(cvss=9.8, exploitability=0.9, exposure=0.9, asset_criticality="critical")
    assert a["score"] == b["score"]
    assert a["band"] == "critical"
    assert "Risk score" in explain_risk_score(a)


def test_ai_investigation_tenant_scoped(tmp_path, monkeypatch):
    data_dir = tmp_path / "inv"
    data_dir.mkdir()
    _reload(monkeypatch, data_dir)
    from app.auth import register_user
    from app.commercial_ext import create_org
    from app.enterprise import create_asset, create_vulnerability
    from app.services.investigation import investigate_top_assets
    from app.tenancy import ensure_tenant_schema

    ensure_tenant_schema()
    alice = register_user("inv_a", "password123", role="user")
    bob = register_user("inv_b", "password123", role="user")
    org_a = create_org(alice.id, "InvOrgA")
    org_b = create_org(bob.id, "InvOrgB")
    create_asset(alice.id, "edge-a", criticality="critical", org_id=org_a["id"])
    create_asset(bob.id, "edge-b", criticality="critical", org_id=org_b["id"])
    create_vulnerability(
        alice.id,
        {"title": "A-only", "severity": "critical", "cvss": 9.8, "asset_name": "edge-a", "org_id": org_a["id"]},
    )
    create_vulnerability(
        bob.id,
        {"title": "B-only", "severity": "critical", "cvss": 9.9, "asset_name": "edge-b", "org_id": org_b["id"]},
    )

    report = investigate_top_assets(alice.id, org_id=org_a["id"], limit=5)
    names = {a["asset"]["name"] for a in report["assets"]}
    titles = {f["title"] for a in report["assets"] for f in a["findings"]}
    assert "edge-a" in names
    assert "edge-b" not in names
    assert "A-only" in titles
    assert "B-only" not in titles
    assert report["steps"][0]["status"] == "done"
