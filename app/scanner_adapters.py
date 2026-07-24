"""Import adapters for mature open-source scanners.

SecuraIQ orchestrates findings — it does not replace the scanners.
Supported: Trivy, Semgrep, Gitleaks, Grype, Checkov, Bandit, SonarQube, OWASP ZAP.
"""

from __future__ import annotations

import json
from typing import Any, Callable


def _sev_norm(sev: str, default: str = "medium") -> str:
    s = (sev or default).strip().upper()
    return {
        "CRITICAL": "critical",
        "BLOCKER": "critical",
        "HIGH": "high",
        "ERROR": "high",
        "MAJOR": "high",
        "MEDIUM": "medium",
        "WARNING": "medium",
        "MINOR": "low",
        "LOW": "low",
        "INFO": "info",
        "INFORMATIONAL": "info",
        "UNKNOWN": "info",
        "NEGLIGIBLE": "info",
        "NEGLLIGIBLE": "info",
    }.get(s, default if default in {"critical", "high", "medium", "low", "info"} else "medium")


def _sev_from_trivy(sev: str) -> str:
    return _sev_norm(sev, "medium")


def _sev_from_semgrep(sev: str) -> str:
    return _sev_norm(sev, "medium")


def _sev_from_zap_risk(riskcode: str | int | None, riskdesc: str = "") -> str:
    try:
        code = int(riskcode) if riskcode is not None and str(riskcode).isdigit() else -1
    except (TypeError, ValueError):
        code = -1
    if code >= 3 or "high" in (riskdesc or "").lower():
        return "high"
    if code == 2 or "medium" in (riskdesc or "").lower():
        return "medium"
    if code == 1 or "low" in (riskdesc or "").lower():
        return "low"
    return "info"


def detect_scanner_format(data: Any, filename: str = "") -> str | None:
    """Return adapter name if payload matches a known scanner."""
    name = (filename or "").lower()
    hints = (
        ("trivy", "trivy"),
        ("semgrep", "semgrep"),
        ("gitleaks", "gitleaks"),
        ("secrets", "gitleaks"),
        ("grype", "grype"),
        ("checkov", "checkov"),
        ("bandit", "bandit"),
        ("sonar", "sonarqube"),
        ("zap", "zap"),
        ("zaproxy", "zap"),
    )
    for needle, kind in hints:
        if needle in name:
            return kind

    if isinstance(data, dict):
        if "Results" in data and isinstance(data.get("Results"), list):
            return "trivy"
        if isinstance(data.get("matches"), list):
            return "grype"
        if "results" in data and isinstance(data.get("results"), dict):
            res = data["results"]
            if isinstance(res.get("failed_checks"), list) or isinstance(res.get("passed_checks"), list):
                return "checkov"
        if isinstance(data.get("failed_checks"), list) and any(
            isinstance(x, dict) and ("check_id" in x or "check_name" in x) for x in (data.get("failed_checks") or [])[:3]
        ):
            return "checkov"
        if isinstance(data.get("issues"), list):
            sample = data["issues"][0] if data["issues"] else {}
            if isinstance(sample, dict) and ("component" in sample or "rule" in sample or "severity" in sample):
                return "sonarqube"
        if isinstance(data.get("site"), list):
            return "zap"
        if "results" in data and isinstance(data.get("results"), list):
            sample = data["results"][0] if data["results"] else {}
            if isinstance(sample, dict):
                if "issue_text" in sample or "issue_severity" in sample or "test_id" in sample:
                    return "bandit"
                if "check_id" in sample or "extra" in sample or ("path" in sample and "start" in sample):
                    return "semgrep"
        if isinstance(data.get("findings"), list):
            sample = data["findings"][0] if data["findings"] else {}
            if isinstance(sample, dict) and ("RuleID" in sample or "Secret" in sample or "Fingerprint" in sample):
                return "gitleaks"

    if isinstance(data, list) and data and isinstance(data[0], dict):
        row = data[0]
        if "RuleID" in row or "Secret" in row:
            return "gitleaks"
        if "check_id" in row and "path" in row:
            return "semgrep"
        if "issue_text" in row or "test_id" in row:
            return "bandit"
    return None


def parse_trivy(data: dict[str, Any], *, engagement_id: str | None, filename: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for result in data.get("Results") or []:
        target = result.get("Target") or result.get("TargetType") or ""
        for vuln in result.get("Vulnerabilities") or []:
            cve = vuln.get("VulnerabilityID") or ""
            title = vuln.get("Title") or vuln.get("PkgName") or cve or "Trivy finding"
            pkg = vuln.get("PkgName") or ""
            if pkg and pkg not in title:
                title = f"{pkg}: {title}"
            items.append(
                {
                    "title": str(title)[:300],
                    "cve": str(cve)[:40],
                    "severity": _sev_from_trivy(str(vuln.get("Severity") or "MEDIUM")),
                    "asset_name": str(target)[:200],
                    "cvss": None,
                    "engagement_id": engagement_id,
                    "source": f"trivy:{filename}",
                    "raw": vuln,
                }
            )
        for mis in result.get("Misconfigurations") or []:
            items.append(
                {
                    "title": str(mis.get("Title") or mis.get("ID") or "Misconfiguration")[:300],
                    "cve": str(mis.get("ID") or "")[:40],
                    "severity": _sev_from_trivy(str(mis.get("Severity") or "MEDIUM")),
                    "asset_name": str(target)[:200],
                    "cvss": None,
                    "engagement_id": engagement_id,
                    "source": f"trivy-misconfig:{filename}",
                    "raw": mis,
                }
            )
        for sec in result.get("Secrets") or []:
            items.append(
                {
                    "title": f"Secret: {sec.get('Title') or sec.get('RuleID') or 'detected'}"[:300],
                    "cve": "",
                    "severity": _sev_from_trivy(str(sec.get("Severity") or "HIGH")),
                    "asset_name": str(sec.get("Target") or target)[:200],
                    "cvss": None,
                    "engagement_id": engagement_id,
                    "source": f"trivy-secret:{filename}",
                    "raw": sec,
                }
            )
    return items


def parse_semgrep(data: dict[str, Any] | list, *, engagement_id: str | None, filename: str) -> list[dict[str, Any]]:
    rows = data.get("results") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        rows = []
    items: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        extra = row.get("extra") or {}
        meta = extra.get("metadata") or {}
        sev = extra.get("severity") or meta.get("severity") or "WARNING"
        path = row.get("path") or ""
        check = row.get("check_id") or meta.get("cwe") or "semgrep"
        msg = extra.get("message") or check
        items.append(
            {
                "title": str(msg)[:300],
                "cve": str(meta.get("cve") or meta.get("cwe") or "")[:40],
                "severity": _sev_from_semgrep(str(sev)),
                "asset_name": str(path)[:200],
                "cvss": None,
                "engagement_id": engagement_id,
                "source": f"semgrep:{filename}",
                "raw": row,
            }
        )
    return items


def parse_gitleaks(data: Any, *, engagement_id: str | None, filename: str) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        rows = data.get("findings") or data.get("leaks") or []
    elif isinstance(data, list):
        rows = data
    else:
        rows = []
    items: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        rule = row.get("RuleID") or row.get("rule") or "secret"
        file_path = row.get("File") or row.get("file") or ""
        desc = row.get("Description") or row.get("description") or rule
        items.append(
            {
                "title": f"Secret leak: {desc}"[:300],
                "cve": "",
                "severity": "high",
                "asset_name": str(file_path)[:200],
                "cvss": None,
                "engagement_id": engagement_id,
                "source": f"gitleaks:{filename}",
                "raw": {k: v for k, v in row.items() if k.lower() not in {"secret", "match", "fingerprint"}},
            }
        )
    return items


def parse_grype(data: dict[str, Any], *, engagement_id: str | None, filename: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for match in data.get("matches") or []:
        if not isinstance(match, dict):
            continue
        vuln = match.get("vulnerability") or {}
        art = match.get("artifact") or {}
        cve = vuln.get("id") or ""
        pkg = art.get("name") or ""
        ver = art.get("version") or ""
        title = f"{pkg}@{ver}: {cve}".strip(": ") if pkg else (vuln.get("description") or cve or "Grype finding")
        items.append(
            {
                "title": str(title)[:300],
                "cve": str(cve)[:40],
                "severity": _sev_norm(str(vuln.get("severity") or "Medium")),
                "asset_name": str(pkg or art.get("locations") or "sbom")[:200],
                "cvss": None,
                "engagement_id": engagement_id,
                "source": f"grype:{filename}",
                "raw": match,
            }
        )
    return items


def parse_checkov(data: dict[str, Any], *, engagement_id: str | None, filename: str) -> list[dict[str, Any]]:
    failed = data.get("failed_checks")
    if failed is None and isinstance(data.get("results"), dict):
        failed = data["results"].get("failed_checks")
    if not isinstance(failed, list):
        failed = []
    items: list[dict[str, Any]] = []
    for row in failed:
        if not isinstance(row, dict):
            continue
        cid = row.get("check_id") or row.get("id") or "checkov"
        name = row.get("check_name") or row.get("name") or cid
        path = row.get("file_path") or row.get("repo_file_path") or row.get("resource") or ""
        items.append(
            {
                "title": f"{cid}: {name}"[:300],
                "cve": str(cid)[:40],
                "severity": _sev_norm(str(row.get("severity") or "MEDIUM")),
                "asset_name": str(path)[:200],
                "cvss": None,
                "engagement_id": engagement_id,
                "source": f"checkov:{filename}",
                "raw": row,
            }
        )
    return items


def parse_bandit(data: dict[str, Any] | list, *, engagement_id: str | None, filename: str) -> list[dict[str, Any]]:
    rows = data.get("results") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        rows = []
    items: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        tid = row.get("test_id") or row.get("test_name") or "bandit"
        msg = row.get("issue_text") or row.get("issue_confidence") or tid
        cwe = row.get("cwe")
        cwe_id = ""
        if isinstance(cwe, dict):
            cwe_id = str(cwe.get("id") or "")
        elif cwe:
            cwe_id = str(cwe)
        items.append(
            {
                "title": f"{tid}: {msg}"[:300],
                "cve": cwe_id[:40],
                "severity": _sev_norm(str(row.get("issue_severity") or "MEDIUM")),
                "asset_name": str(row.get("filename") or "")[:200],
                "cvss": None,
                "engagement_id": engagement_id,
                "source": f"bandit:{filename}",
                "raw": row,
            }
        )
    return items


def parse_sonarqube(data: dict[str, Any], *, engagement_id: str | None, filename: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for issue in data.get("issues") or []:
        if not isinstance(issue, dict):
            continue
        # Prefer security-relevant types when present; still import others as findings
        itype = (issue.get("type") or "").upper()
        msg = issue.get("message") or issue.get("rule") or "SonarQube issue"
        rule = issue.get("rule") or ""
        comp = issue.get("component") or issue.get("project") or ""
        title = f"[{itype or 'CODE'}] {msg}" if itype else str(msg)
        if rule and rule not in title:
            title = f"{rule}: {msg}"
        items.append(
            {
                "title": str(title)[:300],
                "cve": str(rule)[:40],
                "severity": _sev_norm(str(issue.get("severity") or "MAJOR")),
                "asset_name": str(comp)[:200],
                "cvss": None,
                "engagement_id": engagement_id,
                "source": f"sonarqube:{filename}",
                "raw": issue,
            }
        )
    return items


def parse_zap(data: dict[str, Any], *, engagement_id: str | None, filename: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for site in data.get("site") or []:
        if not isinstance(site, dict):
            continue
        host = site.get("@name") or site.get("name") or site.get("@host") or "web-app"
        for alert in site.get("alerts") or []:
            if not isinstance(alert, dict):
                continue
            name = alert.get("name") or alert.get("alert") or "ZAP alert"
            plugin = alert.get("pluginid") or alert.get("pluginId") or ""
            items.append(
                {
                    "title": str(name)[:300],
                    "cve": str(plugin)[:40],
                    "severity": _sev_from_zap_risk(alert.get("riskcode"), str(alert.get("riskdesc") or "")),
                    "asset_name": str(host)[:200],
                    "cvss": None,
                    "engagement_id": engagement_id,
                    "source": f"zap:{filename}",
                    "raw": {k: v for k, v in alert.items() if k != "instances"} | {"instances_count": len(alert.get("instances") or [])},
                }
            )
    return items


ADAPTERS: dict[str, Callable[..., list[dict[str, Any]]]] = {
    "trivy": parse_trivy,
    "semgrep": parse_semgrep,
    "gitleaks": parse_gitleaks,
    "grype": parse_grype,
    "checkov": parse_checkov,
    "bandit": parse_bandit,
    "sonarqube": parse_sonarqube,
    "zap": parse_zap,
}


def try_parse_scanner_json(
    text: str,
    *,
    filename: str,
    engagement_id: str | None,
) -> tuple[str | None, list[dict[str, Any]]]:
    """If JSON matches a scanner, return (adapter_name, normalized items)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None, []
    kind = detect_scanner_format(data, filename)
    if not kind:
        return None, []
    parser = ADAPTERS[kind]
    return kind, parser(data, engagement_id=engagement_id, filename=filename)


def list_import_adapters() -> list[str]:
    return sorted(ADAPTERS.keys())
