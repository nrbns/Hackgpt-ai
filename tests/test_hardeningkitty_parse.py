"""HardeningKitty CSV → vulnerability shaping (asset_name must persist)."""

from __future__ import annotations

from app.hardeningkitty import parse_report_csv, summarize_report


SAMPLE = """ID,Category,Name,Method,Severity,Result,Recommended,TestResult
1,Account Policies,Minimum password length,Registry,High,7,14,Failed
2,Account Policies,Password complexity,Registry,Medium,Enabled,Enabled,Passed
3,User Rights,Debug programs,Registry,Critical,Everyone,Administrators,Failed
"""


def test_parse_skips_passed_and_sets_asset_name():
    items = parse_report_csv(SAMPLE, filename="report.csv")
    assert len(items) == 2
    for it in items:
        assert it.get("asset_name"), "create_vulnerability reads asset_name, not asset"
        assert "asset" not in it or it.get("asset_name")
        assert it["severity"] in {"critical", "high", "medium", "low", "info"}
        assert it["source"].startswith("hardeningkitty:")
    titles = " ".join(i["title"] for i in items)
    assert "Minimum password length" in titles
    assert "Debug programs" in titles
    assert "Password complexity" not in titles


def test_parse_include_passed():
    items = parse_report_csv(SAMPLE, include_passed=True)
    assert len(items) == 3


def test_summarize_counts():
    summary = summarize_report(SAMPLE)
    counts = summary["counts"]
    assert counts["total"] == 3
    assert counts["passed"] == 1
    assert counts["failed"] == 2
