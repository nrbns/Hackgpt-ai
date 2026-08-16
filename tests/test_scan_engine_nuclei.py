"""Nuclei scan-engine adapter — parse/normalize/scope (no nuclei binary required)."""

from __future__ import annotations

from pathlib import Path

from app.scanners.base import RawScanResult, ScanContext
from app.scanners.nuclei import NucleiScanner, parse_nuclei_jsonl, to_nuclei_url
from app.scanners.registry import ENGINE_ENABLED, list_scanners

SAMPLE_JSONL = """
{"template-id":"http-missing-security-headers","info":{"name":"HTTP Missing Security Headers","severity":"info"},"matched-at":"http://192.168.56.101/","host":"192.168.56.101"}
{"template-id":"CVE-2021-44228","info":{"name":"Apache Log4j RCE","severity":"critical","classification":{"cve-id":["CVE-2021-44228"]}},"matched-at":"http://192.168.56.101:8080/","host":"192.168.56.101"}
{"template-id":"exposed-panels","info":{"name":"Exposed Admin Panel","severity":"medium"},"matched-at":"https://app.example.com/admin","host":"app.example.com"}
""".strip()


def test_nuclei_is_engine_enabled():
    assert "nuclei" in ENGINE_ENABLED
    entry = next(s for s in list_scanners() if s["id"] == "nuclei")
    assert entry["engine_enabled"] is True


def test_to_nuclei_url():
    assert to_nuclei_url("example.com") == "https://example.com"
    assert to_nuclei_url("http://lab.local/path") == "http://lab.local/path"
    assert to_nuclei_url("https://x.test/") == "https://x.test"


def test_parse_nuclei_jsonl():
    rows = parse_nuclei_jsonl(SAMPLE_JSONL)
    assert len(rows) == 3
    crit = [r for r in rows if r["severity"] == "critical"]
    assert crit and crit[0]["cve"] == "CVE-2021-44228"


def test_normalize_nuclei_findings(tmp_path):
    sc = NucleiScanner()
    ctx = ScanContext(
        scan_id="n1",
        target="http://192.168.56.101",
        profile="web",
        scope=["192.168.56.0/24"],
        authorized=True,
        evidence_dir=tmp_path,
    )
    (tmp_path / "nuclei.jsonl").write_text(SAMPLE_JSONL, encoding="utf-8")
    raw = RawScanResult(exit_code=0, stdout="", stderr="", artifact_paths=[])
    parsed = sc.parse(raw, ctx)
    normalized = sc.normalize(parsed, ctx)
    assert normalized.summary["scanner"] == "nuclei"
    assert normalized.summary["template_matches"] == 3
    titles = " ".join(f.title for f in normalized.findings)
    assert "Log4j" in titles or "CVE-2021-44228" in titles or "Apache" in titles
    assert any(f.severity == "critical" for f in normalized.findings)


def test_nuclei_scope_blocks():
    sc = NucleiScanner()
    ok, _ = sc.validate_scope("https://evil.example/", ["192.168.56.0/24"])
    assert not ok
    ok2, _ = sc.validate_scope("https://192.168.56.101/", ["192.168.56.0/24"])
    assert ok2


def test_nuclei_validate_target():
    sc = NucleiScanner()
    ok, url = sc.validate_target("app.acme.com")
    assert ok and url.startswith("https://")
    ok2, err = sc.validate_target("host;rm")
    assert not ok2
