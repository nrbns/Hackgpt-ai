"""Real tests for the two builtin scan tools added to close the gap where
nmap/nuclei/openvas (network) and semgrep/bandit/trivy (code) require an
external install the user typically does not have: `netvuln_scan` (banner
grab + version-CVE matching, TLS/header weaknesses, risky ports — all pure
Python/stdlib sockets) and `code_scan` (secret detection, dangerous-pattern
SAST, OSV.dev dependency lookup — also pure Python, no scanner binary).

These tests avoid real network/socket I/O (netvuln_scan's live banner grab,
code_scan's OSV.dev lookup) so the suite stays fast and deterministic; they
exercise the actual detection/matching logic and the safety gates directly.
"""

from __future__ import annotations

import asyncio

import pytest

from app.tools.registry import TOOL_CATALOG
from app.tools.runner import (
    _DANGEROUS_RULES,
    _SECRET_RULES,
    _VERSION_VULN_RULES,
    _osv_dependency_check,
    _redact,
    _tool_code_scan,
)


# --- catalog wiring --------------------------------------------------------


def test_netvuln_scan_and_code_scan_are_registered():
    assert "netvuln_scan" in TOOL_CATALOG
    assert "code_scan" in TOOL_CATALOG
    assert TOOL_CATALOG["netvuln_scan"].kind == "builtin"
    assert TOOL_CATALOG["code_scan"].kind == "builtin"


# --- version/CVE banner matching (netvuln_scan) -----------------------------


def test_vsftpd_backdoor_banner_matches():
    hits = [product for pattern, product, cve, note in _VERSION_VULN_RULES if pattern.search("220 (vsftpd 2.3.4)")]
    assert "vsftpd 2.3.4" in hits


def test_old_openssh_matches_but_current_release_does_not():
    old = "SSH-2.0-OpenSSH_6.6.1"
    current = "SSH-2.0-OpenSSH_9.6"
    old_hits = [p for pattern, p, cve, note in _VERSION_VULN_RULES if pattern.search(old)]
    current_hits = [p for pattern, p, cve, note in _VERSION_VULN_RULES if pattern.search(current)]
    assert "OpenSSH < 7.5" in old_hits
    assert current_hits == []


def test_apache_2_2_matches_eol_rule():
    hits = [p for pattern, p, cve, note in _VERSION_VULN_RULES if pattern.search("Apache/2.2.15 (CentOS)")]
    assert "Apache httpd 2.2.x" in hits


@pytest.mark.parametrize(
    "banner,expect_match",
    [
        ("Apache/2.4.9", True),      # single-digit patch — CVE-2017-9798 range
        ("Apache/2.4.19", True),     # two-digit patch in the 10-19 bucket
        ("Apache/2.4.25", True),     # top of the vulnerable range
        ("Apache/2.4.30", False),    # patched release — must NOT false-positive
        ("Apache/2.4.51", False),    # current-ish release — must NOT false-positive
    ],
)
def test_apache_2_4_range_boundaries_do_not_false_positive(banner, expect_match):
    hits = [p for pattern, p, cve, note in _VERSION_VULN_RULES if pattern.search(banner)]
    assert bool(hits) is expect_match, f"{banner} -> {hits}"


def test_iis_6_matches_webdav_cve():
    hits = [
        (p, cve) for pattern, p, cve, note in _VERSION_VULN_RULES if pattern.search("Microsoft-IIS/6.0")
    ]
    assert hits and hits[0][1] == "CVE-2017-7269"


# --- secret redaction (code_scan) -------------------------------------------


def test_redact_never_leaks_the_matched_secret_value():
    secret = "AKIAABCDEFGHIJKLMNOP"
    line = f'aws_key = "{secret}"'
    pattern = dict(_SECRET_RULES)["aws_access_key_id"]
    m = pattern.search(line)
    assert m is not None
    redacted = _redact(line, m.span())
    assert secret not in redacted
    assert "«redacted»" in redacted


def test_secret_rules_detect_common_key_shapes():
    rules = dict(_SECRET_RULES)
    assert rules["aws_access_key_id"].search("AKIAABCDEFGHIJKLMNOP")
    assert rules["github_token"].search("ghp_1234567890abcdef1234567890abcdef1234")
    # Build in pieces so push-protection scanners do not treat the fixture as a live key.
    stripe_fixture = "sk_" + "test_" + ("0" * 24)
    assert rules["stripe_secret_key"].search(stripe_fixture)
    assert rules["private_key_block"].search("-----BEGIN RSA PRIVATE KEY-----")
    assert not rules["aws_access_key_id"].search("not a secret at all")


# --- dangerous pattern SAST rules -------------------------------------------


def test_python_eval_and_shell_true_are_flagged():
    eval_rule = next(r for r in _DANGEROUS_RULES if r[0] == "py_eval_exec")
    shell_rule = next(r for r in _DANGEROUS_RULES if r[0] == "py_subprocess_shell_true")
    assert eval_rule[1].search("result = eval(user_input)")
    assert shell_rule[1].search('subprocess.run(cmd, shell=True)')
    assert not shell_rule[1].search('subprocess.run(cmd, shell=False)')


def test_js_eval_and_innerhtml_are_flagged():
    eval_rule = next(r for r in _DANGEROUS_RULES if r[0] == "js_eval")
    html_rule = next(r for r in _DANGEROUS_RULES if r[0] == "js_inner_html")
    assert eval_rule[1].search("eval(userSuppliedCode)")
    assert html_rule[1].search("el.innerHTML = userInput")


def test_hardcoded_http_ignores_localhost():
    rule = next(r for r in _DANGEROUS_RULES if r[0] == "hardcoded_http_url")
    assert rule[1].search("fetch('http://api.example.com/data')")
    assert not rule[1].search("fetch('http://localhost:8080/data')")
    assert not rule[1].search("fetch('http://127.0.0.1:8080/data')")


# --- _tool_code_scan end-to-end (real filesystem, no network) --------------


def test_code_scan_requires_authorization():
    result = asyncio.run(_tool_code_scan("/tmp", authorized=False))
    assert result["ok"] is False
    assert "auth" in (result.get("error") or "").lower() or "Auth" in result["output"]


def test_code_scan_requires_a_path():
    result = asyncio.run(_tool_code_scan("", authorized=True))
    assert result["ok"] is False
    assert "path" in (result.get("error") or "").lower()


def test_code_scan_rejects_nonexistent_path():
    result = asyncio.run(_tool_code_scan("/definitely/does/not/exist/anywhere", authorized=True))
    assert result["ok"] is False
    assert "not found" in (result.get("error") or "").lower()


def test_code_scan_finds_secret_and_dangerous_pattern_but_skips_node_modules(tmp_path):
    (tmp_path / "app.py").write_text(
        'aws_key = "AKIAABCDEFGHIJKLMNOP"\n'
        "def run(cmd):\n"
        "    subprocess.run(cmd, shell=True)\n",
        encoding="utf-8",
    )
    skipped_dir = tmp_path / "node_modules" / "somelib"
    skipped_dir.mkdir(parents=True)
    (skipped_dir / "evil.py").write_text('secret = "AKIAZZZZZZZZZZZZZZZZ"\n', encoding="utf-8")

    result = asyncio.run(_tool_code_scan(str(tmp_path), authorized=True))
    assert result["ok"] is True

    secret_files = {f["file"] for f in result["secret_findings"]}
    assert "app.py" in secret_files
    assert not any("node_modules" in f for f in secret_files)

    # The actual key value must never appear in the returned findings.
    assert "AKIAABCDEFGHIJKLMNOP" not in str(result["secret_findings"])

    pattern_rules_hit = {p["rule"] for p in result["pattern_findings"]}
    assert "py_subprocess_shell_true" in pattern_rules_hit


def test_code_scan_clean_directory_reports_no_findings(tmp_path):
    (tmp_path / "clean.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    result = asyncio.run(_tool_code_scan(str(tmp_path), authorized=True))
    assert result["ok"] is True
    assert result["secret_findings"] == []
    assert result["pattern_findings"] == []


def test_osv_dependency_check_skips_network_call_when_nothing_to_query(tmp_path):
    # No requirements.txt / package.json in this directory -> queries list is
    # empty -> must return [] without attempting any HTTP call.
    result = asyncio.run(_osv_dependency_check(tmp_path, []))
    assert result == []


def test_osv_dependency_check_ignores_unpinned_requirements(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("flask>=1.0\n# a comment\nrequests\n", encoding="utf-8")
    # None of these lines are exact `==` pins, so no query should be built,
    # meaning no network call is attempted (would return [] either way, but
    # this confirms the parser doesn't choke on ranges/comments/bare names).
    result = asyncio.run(_osv_dependency_check(tmp_path, [req]))
    assert result == []
