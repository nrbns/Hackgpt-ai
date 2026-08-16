"""Cross-tenant isolation: Org A must never see Org B data."""

from __future__ import annotations

import importlib

import pytest


def _reload(monkeypatch, data_dir):
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("WORKSPACE_ZERO_START", "false")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("DEPLOYMENT_MODE", "lab")
    monkeypatch.setenv("DATABASE_URL", "")
    import app.config as config_mod
    import app.db as db_mod

    importlib.reload(config_mod)
    db_mod.reset_conn_for_tests()
    importlib.reload(db_mod)
    return config_mod, db_mod


@pytest.fixture()
def two_orgs(tmp_path, monkeypatch):
    data_dir = tmp_path / "tenant"
    data_dir.mkdir()
    _reload(monkeypatch, data_dir)
    from app.auth import register_user
    from app.commercial_ext import create_org
    from app.tenancy import ensure_tenant_schema

    ensure_tenant_schema()
    alice = register_user("alice_iso", "password123", role="user")
    bob = register_user("bob_iso", "password123", role="user")
    org_a = create_org(alice.id, "OrgA-Iso")
    org_b = create_org(bob.id, "OrgB-Iso")
    return alice, bob, org_a, org_b


def test_vuln_and_risk_isolation(two_orgs):
    alice, bob, org_a, org_b = two_orgs
    from app.enterprise import create_asset, create_risk, create_vulnerability, list_risks, list_vulnerabilities

    create_asset(alice.id, "host-a", org_id=org_a["id"])
    create_asset(bob.id, "host-b", org_id=org_b["id"])
    create_vulnerability(
        alice.id,
        {"title": "Alice finding", "severity": "high", "asset_name": "host-a", "org_id": org_a["id"]},
    )
    create_vulnerability(
        bob.id,
        {"title": "Bob finding", "severity": "critical", "asset_name": "host-b", "org_id": org_b["id"]},
    )
    create_risk(alice.id, threat="Alice threat", asset_name="host-a", org_id=org_a["id"])
    create_risk(bob.id, threat="Bob threat", asset_name="host-b", org_id=org_b["id"])

    alice_vulns = {v["title"] for v in list_vulnerabilities(alice.id, org_id=org_a["id"])}
    bob_vulns = {v["title"] for v in list_vulnerabilities(bob.id, org_id=org_b["id"])}
    assert "Alice finding" in alice_vulns
    assert "Bob finding" not in alice_vulns
    assert "Bob finding" in bob_vulns
    assert "Alice finding" not in bob_vulns

    alice_risks = {r["threat"] for r in list_risks(alice.id, org_id=org_a["id"])}
    bob_risks = {r["threat"] for r in list_risks(bob.id, org_id=org_b["id"])}
    assert "Alice threat" in alice_risks
    assert "Bob threat" not in alice_risks
    assert "Bob threat" in bob_risks
    assert "Alice threat" not in bob_risks


def test_chat_and_engagement_isolation(two_orgs):
    alice, bob, org_a, org_b = two_orgs
    from app.workspace import create_chat, create_engagement, list_chats, list_engagements

    ea = create_engagement(alice.id, "Eng-A", scope_json=["10.0.0.0/8"])
    eb = create_engagement(bob.id, "Eng-B", scope_json=["192.168.0.0/16"])
    create_chat(alice.id, title="Alice chat", engagement_id=ea["id"])
    create_chat(bob.id, title="Bob chat", engagement_id=eb["id"])

    alice_eng = {e["name"] for e in list_engagements(alice.id)}
    bob_eng = {e["name"] for e in list_engagements(bob.id)}
    assert "Eng-A" in alice_eng and "Eng-B" not in alice_eng
    assert "Eng-B" in bob_eng and "Eng-A" not in bob_eng

    alice_chats = {c["title"] for c in list_chats(alice.id)}
    bob_chats = {c["title"] for c in list_chats(bob.id)}
    assert "Alice chat" in alice_chats
    assert "Bob chat" not in alice_chats
    assert "Bob chat" in bob_chats
    assert "Alice chat" not in bob_chats

    # org ids unused here but prove fixture still yields distinct orgs
    assert org_a["id"] != org_b["id"]


def test_tool_scope_blocks_cross_engagement_target(two_orgs):
    alice, _bob, _oa, _ob = two_orgs
    from app.services.tool_policy import assert_tool_target_allowed
    from app.workspace import create_engagement

    eng = create_engagement(alice.id, "Scoped", scope_json=["10.0.0.0/8"])
    assert_tool_target_allowed(
        user_id=alice.id,
        engagement_id=eng["id"],
        target="10.1.2.3",
        ip="10.1.2.3",
        authorized=True,
    )
    with pytest.raises(ValueError, match="out of engagement scope"):
        assert_tool_target_allowed(
            user_id=alice.id,
            engagement_id=eng["id"],
            target="8.8.8.8",
            ip="8.8.8.8",
            authorized=True,
        )
