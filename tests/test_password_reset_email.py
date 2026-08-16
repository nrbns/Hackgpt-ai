"""Real behavioral test for the password-reset security fix: when a user has
an email on file and SMTP is configured, the reset token must be emailed and
never appear in the API response — proving mailbox ownership is the entire
point of a reset flow. Before this fix, request_password_reset() always
returned the raw token in-band, letting anyone who could call the endpoint
for a known username take over that account without ever touching its inbox.

Also covers: registering with an email persists it, and org_id gets stamped
on risks/playbooks/campaigns/gap-remediations at creation time (the write
side of the tenant-isolation fix — list_risks/list_playbooks/etc. only see
shared org data if create_* actually stamped org_id in the first place).
"""

from __future__ import annotations

import importlib

import pytest


def _reload_db(monkeypatch, data_dir):
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("WORKSPACE_ZERO_START", "false")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("DEPLOYMENT_MODE", "lab")
    import app.config as config_mod
    import app.db as db_mod

    importlib.reload(config_mod)
    db_mod._conn = None
    importlib.reload(db_mod)
    return config_mod, db_mod


def test_register_with_email_persists_it(tmp_path, monkeypatch):
    _reload_db(monkeypatch, tmp_path / "d1")
    from app.auth import register_user
    from app.db import get_conn

    register_user("hasemail", "password123", email="Person@Example.com")
    row = get_conn().execute(
        "SELECT email FROM users WHERE username = ?", ("hasemail",)
    ).fetchone()
    # Stored lowercased, and NOT NULL (never None) — the exact column
    # convention is `email TEXT NOT NULL DEFAULT ''` in app.db._migrate_users.
    assert row["email"] == "person@example.com"


def test_register_without_email_stores_empty_string_not_null(tmp_path, monkeypatch):
    _reload_db(monkeypatch, tmp_path / "d2")
    from app.auth import register_user
    from app.db import get_conn

    register_user("noemail", "password123")
    row = get_conn().execute(
        "SELECT email FROM users WHERE username = ?", ("noemail",)
    ).fetchone()
    assert row["email"] == ""  # not None — the column is NOT NULL


def test_reset_emails_token_and_never_returns_it_when_deliverable(tmp_path, monkeypatch):
    _reload_db(monkeypatch, tmp_path / "d3")
    import app.notifications as notifications_mod
    from app.auth import register_user, request_password_reset

    register_user("willreset", "password123", email="willreset@example.com")

    sent: dict[str, str] = {}

    def _fake_send_email(to_addr: str, subject: str, body: str) -> bool:
        sent["to"] = to_addr
        sent["subject"] = subject
        sent["body"] = body
        return True

    monkeypatch.setattr(notifications_mod, "_smtp_configured", lambda: True)
    monkeypatch.setattr(notifications_mod, "send_email", _fake_send_email)

    out = request_password_reset("willreset")
    assert out["ok"] is True
    # This is the actual security property: the token must never be handed
    # back in the API response once it was deliverable by email.
    assert "reset_token" not in out
    assert sent["to"] == "willreset@example.com"
    assert "reset" in sent["subject"].lower()


def test_reset_falls_back_to_in_band_token_when_no_email_on_file(tmp_path, monkeypatch):
    _reload_db(monkeypatch, tmp_path / "d4")
    from app.auth import register_user, request_password_reset

    register_user("noemailreset", "password123")  # no email on file
    out = request_password_reset("noemailreset")
    assert out["ok"] is True
    # No email to send to -> the lab/local fallback path, token in response,
    # and the response should say so rather than pretending it was emailed.
    assert out.get("reset_token")
    assert "smtp" in out["message"].lower() or "email" in out["message"].lower()


def test_reset_falls_back_when_smtp_not_configured_even_with_email(tmp_path, monkeypatch):
    _reload_db(monkeypatch, tmp_path / "d5")
    import app.notifications as notifications_mod
    from app.auth import register_user, request_password_reset

    register_user("hasemailnosmtp", "password123", email="x@example.com")
    monkeypatch.setattr(notifications_mod, "_smtp_configured", lambda: False)

    out = request_password_reset("hasemailnosmtp")
    assert out.get("reset_token")  # SMTP not configured -> can't deliver -> fallback


def test_org_id_stamped_on_risk_playbook_campaign_remediation_creation(tmp_path, monkeypatch):
    _reload_db(monkeypatch, tmp_path / "d6")
    from app.auth import register_user
    from app.commercial_ext import create_org
    from app.enterprise import (
        create_campaign,
        create_playbook,
        create_remediations_from_assessment,
        create_risk,
        list_campaigns,
        list_playbooks,
        list_remediations,
        list_risks,
    )

    from app.db import get_conn, now

    alice = register_user("alice_org", "password123")
    bob = register_user("bob_org", "password123")
    org_a = create_org(alice.id, "OrgA")
    org_b = create_org(bob.id, "OrgB")

    # gap_remediations.assessment_id has a FK to gap_assessments(id) — seed
    # the minimal rows create_remediations_from_assessment needs.
    c = get_conn()
    for aid, uid in (("assess-a", alice.id), ("assess-b", bob.id)):
        c.execute(
            "INSERT INTO gap_assessments (id, user_id, framework_id, title, result_json, created_at) "
            "VALUES (?, ?, 'owasp_top10', 'test', '{}', ?)",
            (aid, uid, now()),
        )
    c.commit()

    create_risk(alice.id, threat="phishing", org_id=org_a["id"])
    create_risk(bob.id, threat="ransomware", org_id=org_b["id"])
    create_playbook(alice.id, title="IR plan A", org_id=org_a["id"])
    create_playbook(bob.id, title="IR plan B", org_id=org_b["id"])
    create_campaign(alice.id, name="Phish sim A", org_id=org_a["id"])
    create_campaign(bob.id, name="Phish sim B", org_id=org_b["id"])
    create_remediations_from_assessment(
        alice.id, "assess-a", [{"status": "missing", "title": "Control A", "control_id": "c1"}],
        org_id=org_a["id"],
    )
    create_remediations_from_assessment(
        bob.id, "assess-b", [{"status": "missing", "title": "Control B", "control_id": "c1"}],
        org_id=org_b["id"],
    )

    alice_risks = {r["threat"] for r in list_risks(alice.id, org_id=org_a["id"])}
    bob_risks = {r["threat"] for r in list_risks(bob.id, org_id=org_b["id"])}
    assert alice_risks == {"phishing"}
    assert bob_risks == {"ransomware"}

    alice_playbooks = {p["title"] for p in list_playbooks(alice.id, org_id=org_a["id"])}
    assert alice_playbooks == {"IR plan A"}

    alice_campaigns = {c["name"] for c in list_campaigns(alice.id, org_id=org_a["id"])}
    assert alice_campaigns == {"Phish sim A"}

    alice_rems = {r["title"] for r in list_remediations(alice.id, org_id=org_a["id"])}
    assert alice_rems == {"Control A"}
