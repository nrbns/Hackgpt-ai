"""OWASP ZAP scanner adapter — baseline / quick web assessment.

Requires `zap-baseline.py` or `zap`/`zaproxy` on PATH. Writes JSON evidence when
baseline `-J` is available; otherwise parses text output into findings.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from typing import Any

from app.scanners.base import (
    NormalizedFinding,
    NormalizedScan,
    NormalizedService,
    RawScanResult,
    ScanContext,
    Scanner,
)
from app.scanners.constants import HOST_OR_IP
from app.scanners.nuclei import _hostname_from_target, to_nuclei_url
from app.services.tool_policy import target_in_scope

_TIMEOUT = {
    "discovery": 90.0,
    "web": 180.0,
    "vulnerability": 240.0,
    "full": 360.0,
}


def _sev_from_zap_risk(riskcode: str | int | None, riskdesc: str = "") -> str:
    try:
        code = int(riskcode) if riskcode is not None and str(riskcode).strip() != "" else -1
    except (TypeError, ValueError):
        code = -1
    if code >= 3 or "high" in (riskdesc or "").lower():
        return "high"
    if code == 2 or "medium" in (riskdesc or "").lower():
        return "medium"
    if code == 1 or "low" in (riskdesc or "").lower():
        return "low"
    return "info"


def parse_zap_json(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse ZAP JSON report (site[].alerts[]) into intermediate rows."""
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
                    "severity": _sev_from_zap_risk(alert.get("riskcode"), str(alert.get("riskdesc") or "")),
                    "asset_name": str(host)[:200],
                    "plugin": str(plugin),
                    "raw": {
                        k: v
                        for k, v in alert.items()
                        if k != "instances"
                    }
                    | {"instances_count": len(alert.get("instances") or [])},
                }
            )
    return items[:150]


def parse_zap_baseline_text(text: str, *, asset: str) -> list[dict[str, Any]]:
    """Best-effort parse of zap-baseline.py console lines (WARN-/FAIL- style)."""
    items: list[dict[str, Any]] = []
    for line in (text or "").splitlines():
        line = line.strip()
        m = re.match(r"^(WARN|FAIL|INFO)-(\w+)\s+(.*)$", line, re.I)
        if not m:
            continue
        level, code, rest = m.group(1).upper(), m.group(2), m.group(3).strip()
        sev = {"FAIL": "high", "WARN": "medium", "INFO": "info"}.get(level, "info")
        items.append(
            {
                "title": (rest or code)[:300],
                "severity": sev,
                "asset_name": asset[:200],
                "plugin": code,
                "raw": {"line": line, "level": level},
            }
        )
    return items[:80]


def _resolve_zap_binary() -> tuple[str | None, str]:
    baseline = shutil.which("zap-baseline.py") or shutil.which("zap-baseline")
    if baseline:
        return baseline, "baseline"
    for name in ("zap.sh", "zap", "zaproxy"):
        path = shutil.which(name)
        if path:
            return path, "zap"
    return None, ""


class ZapScanner(Scanner):
    id = "zap"
    name = "OWASP ZAP"
    profiles = ("discovery", "web", "vulnerability", "full")

    def available(self) -> tuple[bool, str]:
        path, kind = _resolve_zap_binary()
        if path:
            return True, f"{path} ({kind})"
        return False, "ZAP not on PATH — install OWASP ZAP or set INSTALL_ZAP=true in Docker build"

    def validate_target(self, target: str) -> tuple[bool, str]:
        t = (target or "").strip()
        if not t:
            return False, "target required"
        if any(c in t for c in ";&|`$()<>"):
            return False, "invalid target characters"
        host = _hostname_from_target(t)
        if not host or not HOST_OR_IP.match(host):
            return False, "target must be hostname, IPv4, or http(s) URL"
        return True, to_nuclei_url(t)

    def validate_scope(self, target: str, scope: list[str]) -> tuple[bool, str]:
        host = _hostname_from_target(target)
        ok, reason = target_in_scope(target=host or target, ip=None, scope=scope)
        if ok:
            return True, reason
        return False, f"target out of engagement scope ({reason})"

    def build_command(self, ctx: ScanContext) -> list[str]:
        path, kind = _resolve_zap_binary()
        if not path:
            raise RuntimeError(self.available()[1])
        ok_t, url = self.validate_target(ctx.target)
        if not ok_t:
            raise ValueError(url)
        json_path = ctx.evidence_dir / "zap.json"
        if kind == "baseline":
            # -J writes JSON report; -I ignores WARN exit codes
            return [path, "-t", url, "-J", str(json_path), "-I"]
        return [path, "-cmd", "-quickurl", url, "-quickprogress"]

    async def execute(self, ctx: ScanContext) -> RawScanResult:
        ctx.evidence_dir.mkdir(parents=True, exist_ok=True)
        argv = self.build_command(ctx)
        profile = (ctx.profile or "web").lower()
        timeout = _TIMEOUT.get(profile, 180.0)
        json_path = ctx.evidence_dir / "zap.json"

        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            code = int(proc.returncode or 0)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            stdout_b, stderr_b = b"", b"zap timed out"
            code = -1

        stdout = (stdout_b or b"").decode("utf-8", errors="replace")
        stderr = (stderr_b or b"").decode("utf-8", errors="replace")
        (ctx.evidence_dir / "stdout.log").write_text(stdout, encoding="utf-8")
        (ctx.evidence_dir / "stderr.log").write_text(stderr, encoding="utf-8")
        (ctx.evidence_dir / "command.txt").write_text(" ".join(argv), encoding="utf-8")

        artifacts = [
            str(ctx.evidence_dir / "command.txt"),
            str(ctx.evidence_dir / "stdout.log"),
            str(ctx.evidence_dir / "stderr.log"),
        ]
        if json_path.exists() and json_path.stat().st_size > 0:
            artifacts.insert(0, str(json_path))

        return RawScanResult(
            exit_code=code,
            stdout=stdout,
            stderr=stderr,
            artifact_paths=artifacts,
            meta={"argv": argv, "timeout": timeout},
        )

    def parse(self, raw: RawScanResult, ctx: ScanContext) -> list[dict[str, Any]]:
        json_path = ctx.evidence_dir / "zap.json"
        if json_path.exists() and json_path.stat().st_size > 0:
            try:
                data = json.loads(json_path.read_text(encoding="utf-8", errors="replace"))
                if isinstance(data, dict):
                    return parse_zap_json(data)
            except Exception:
                pass
        # Some baseline versions print JSON to stdout
        text = (raw.stdout or "").strip()
        if text.startswith("{"):
            try:
                data = json.loads(text)
                if isinstance(data, dict) and ("site" in data or "@version" in data):
                    return parse_zap_json(data)
            except Exception:
                pass
        ok_t, url = self.validate_target(ctx.target)
        host = _hostname_from_target(url if ok_t else ctx.target) or ctx.target
        return parse_zap_baseline_text(raw.stdout or "", asset=str(host))

    def normalize(self, parsed: Any, ctx: ScanContext) -> NormalizedScan:
        rows = parsed if isinstance(parsed, list) else []
        ok_t, url = self.validate_target(ctx.target)
        host = _hostname_from_target(url if ok_t else ctx.target) or (ctx.target or "unknown")

        findings: list[NormalizedFinding] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            asset = _hostname_from_target(str(row.get("asset_name") or "")) or host
            findings.append(
                NormalizedFinding(
                    title=str(row.get("title") or "ZAP finding")[:300],
                    severity=str(row.get("severity") or "info"),
                    asset_name=asset[:200],
                    source=f"zap:{row.get('plugin') or 'scan'}",
                    evidence=str(row.get("asset_name") or url if ok_t else ctx.target)[:500],
                    raw=row.get("raw") if isinstance(row.get("raw"), dict) else row,
                )
            )

        if findings:
            findings.insert(
                0,
                NormalizedFinding(
                    title=f"ZAP reported {len(rows)} alert(s) on {host}",
                    severity="info",
                    asset_name=host,
                    source="zap:summary",
                    evidence=f"profile={ctx.profile}",
                    raw={"count": len(rows)},
                ),
            )

        services: list[NormalizedService] = []
        if ok_t and url.startswith("https://"):
            services.append(NormalizedService(port=443, protocol="tcp", state="open", service="https"))
        elif ok_t:
            services.append(NormalizedService(port=80, protocol="tcp", state="open", service="http"))

        return NormalizedScan(
            asset_name=host,
            asset_type="url",
            services=services,
            findings=findings,
            technologies=[],
            summary={
                "open_ports": len(services),
                "findings": len(findings),
                "alerts": len(rows),
                "scanner": "zap",
                "profile": ctx.profile,
                "url": url if ok_t else ctx.target,
            },
        )
