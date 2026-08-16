"""Gap analysis catalog + scoring smoke tests."""

from __future__ import annotations

from app.gap_analysis import (
    list_frameworks,
    load_framework,
    run_gap_analysis,
    score_control_against_evidence,
)


def test_frameworks_catalog_populated():
    fws = list_frameworks()
    ids = {f["id"] for f in fws}
    assert len(fws) >= 14
    assert "iso27001" in ids
    assert "nist_csf" in ids
    assert "cis_controls" in ids


def test_framework_aliases():
    fw = load_framework("cis")
    assert fw["id"] == "cis_controls"
    assert len(fw.get("controls") or []) >= 10


def test_score_control_keywords():
    control = {
        "id": "A.5.1",
        "title": "Policies for information security",
        "keywords": ["information security policy", "management approval", "policy"],
        "description": "Policies for information security",
    }
    missing = score_control_against_evidence(control, "")
    assert missing["status"] == "missing"
    hit = score_control_against_evidence(
        control,
        "Our information security policy has management approval and is reviewed annually.",
    )
    assert hit["status"] in {"implemented", "partial"}
    assert hit["matched_keywords"]


def test_run_gap_analysis_creates_assessment_and_rems(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    # Re-bind settings/data path used by get_conn if needed — assessments use default DB.
    # Use unique user so we don't collide with other tests.
    uid = "gap-test-user"
    evidence = (
        "information security policy approved by management MFA multi-factor authentication "
        "EDR endpoint detection vulnerability scanning backups restore tests incident response "
        "playbook phishing awareness training access control risk assessment"
    )
    result = run_gap_analysis(
        framework_id="owasp_top10",
        evidence=evidence,
        title="unit gap",
        user_id=uid,
    )
    assert result["framework_id"] == "owasp_top10"
    assert "compliance_percent" in result
    assert result["control_count"] >= 5
    assert isinstance(result.get("top_gaps"), list)
    assert result.get("remediations_created", 0) >= 0
    assert result.get("id")
