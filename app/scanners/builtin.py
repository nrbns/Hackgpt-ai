"""Built-in SecuraIQ scanner adapter — zero external install required.

Real gap found via live end-to-end testing: the "New scan" golden path
(POST /api/scans -> app/scan_engine/executor.py) only ever had one engine
registered — Nmap — and Nmap is not installed on most users' machines
(especially Windows), so `scanner.available()` returns False and every scan
fails immediately with a 503 "nmap not found on PATH" before it ever runs.
The tools-palette path already has no-install equivalents (netvuln_scan,
code_scan); the scan-engine golden path did not.

This reuses the exact same pure-Python async port probe + banner grab
already proven in app/tools/runner.py (the code behind the tools palette's
`ports`/`netvuln_scan` tools) so "New scan" always has a scanner that
actually runs out of the box. It checks a curated list of common ports
(not a full 1-65535 sweep) — Nmap remains the deeper option whenever it's
actually installed; this is the honest, always-available floor under it.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from app.scanners.base import (
    NormalizedFinding,
    NormalizedScan,
    NormalizedService,
    RawScanResult,
    ScanContext,
    Scanner,
)
from app.exposure import WINDOWS_LAN_PORTS, network_scope, severity_for_risky_port
from app.scanners.constants import HOST_OR_IP as _HOST_OR_IP
from app.scanners.constants import RISKY_PORTS as _RISKY
from app.services.tool_policy import target_in_scope
from app.tools.runner import (
    _BANNER_GRAB_PORTS,
    _COMMON_PORTS,
    _LIGHT_PORTS,
    _grab_banner,
    _probe_port,
)

_PROFILE_PORTS: dict[str, list[int]] = {
    "discovery": _LIGHT_PORTS,
    "web": [80, 443, 8080, 8443, 8000, 3000],
    "vulnerability": _COMMON_PORTS,
    "full": _COMMON_PORTS,
}

_KNOWN_SERVICES = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns", 80: "http",
    110: "pop3", 111: "rpcbind", 135: "msrpc", 139: "netbios", 143: "imap",
    443: "https", 445: "smb", 1433: "mssql", 1521: "oracle", 2049: "nfs",
    3000: "http-alt", 3306: "mysql", 3389: "rdp", 5432: "postgres",
    5900: "vnc", 5985: "winrm", 6379: "redis", 8009: "ajp", 8080: "http-alt",
    8180: "http-alt", 8443: "https-alt", 9200: "elasticsearch", 27017: "mongodb",
}


class BuiltinScanner(Scanner):
    id = "securaiq"
    name = "SecuraIQ Scanner (built-in, no install)"
    profiles = ("discovery", "web", "vulnerability", "full")

    def available(self) -> tuple[bool, str]:
        return True, "built-in — pure Python async sockets, no external binary required"

    def validate_target(self, target: str) -> tuple[bool, str]:
        t = (target or "").strip()
        if not t:
            return False, "target required"
        if t.startswith("-") or any(c in t for c in ";&|`$()<>"):
            return False, "invalid target characters"
        t2 = re.sub(r"^https?://", "", t, flags=re.I).split("/")[0].split(":")[0]
        if not _HOST_OR_IP.match(t2):
            return False, "target must be hostname or IPv4"
        return True, t2

    def validate_scope(self, target: str, scope: list[str]) -> tuple[bool, str]:
        ok, reason = target_in_scope(target=target, ip=None, scope=scope)
        if ok:
            return True, reason
        return False, f"target out of engagement scope ({reason})"

    def build_command(self, ctx: ScanContext) -> list[str]:
        # No subprocess is spawned — kept as a synthetic command string for
        # evidence/audit parity with the nmap adapter (command.txt artifact).
        ok_t, target = self.validate_target(ctx.target)
        profile = (ctx.profile or "discovery").lower()
        ports = _PROFILE_PORTS.get(profile, _LIGHT_PORTS)
        return [
            "securaiq-builtin-scan",
            "--target", target if ok_t else ctx.target,
            "--profile", profile,
            "--ports", str(len(ports)),
        ]

    async def execute(self, ctx: ScanContext) -> RawScanResult:
        ctx.evidence_dir.mkdir(parents=True, exist_ok=True)
        argv = self.build_command(ctx)
        ok_t, target = self.validate_target(ctx.target)
        if not ok_t:
            raise ValueError(target)
        profile = (ctx.profile or "discovery").lower()
        ports = _PROFILE_PORTS.get(profile, _LIGHT_PORTS)

        flags = await asyncio.gather(*[_probe_port(target, p) for p in ports])
        open_ports = [p for p, ok in zip(ports, flags) if ok]

        banners: dict[int, str] = {}
        banner_ports = [p for p in open_ports if p in _BANNER_GRAB_PORTS]
        if banner_ports:
            grabbed = await asyncio.gather(*[_grab_banner(target, p) for p in banner_ports])
            banners = {p: b for p, b in zip(banner_ports, grabbed) if b}

        result = {
            "target": target,
            "open_ports": open_ports,
            "banners": banners,
            "checked_ports": len(ports),
        }
        ev_json = ctx.evidence_dir / "securaiq_scan.json"
        ev_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
        (ctx.evidence_dir / "command.txt").write_text(" ".join(argv), encoding="utf-8")

        banner_lines = "\n".join(f"{p}: {b}" for p, b in banners.items())
        stdout = (
            f"Open ports ({profile}): {open_ports or 'none'} — checked {len(ports)} ports"
            + (f"\n{banner_lines}" if banner_lines else "")
        )
        return RawScanResult(
            exit_code=0,
            stdout=stdout,
            stderr="",
            artifact_paths=[str(ev_json), str(ctx.evidence_dir / "command.txt")],
            meta={"argv": argv, "scan_result": result},
        )

    def parse(self, raw: RawScanResult, ctx: ScanContext) -> dict[str, Any]:
        data = (raw.meta or {}).get("scan_result")
        if isinstance(data, dict):
            return data
        # Fallback: re-read the evidence file if meta wasn't carried through.
        ev_json = ctx.evidence_dir / "securaiq_scan.json"
        if ev_json.exists():
            try:
                return json.loads(ev_json.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"target": ctx.target, "open_ports": [], "banners": {}, "checked_ports": 0}

    def normalize(self, parsed: Any, ctx: ScanContext) -> NormalizedScan:
        data = parsed if isinstance(parsed, dict) else {}
        ok_t, target = self.validate_target(ctx.target)
        host = target if ok_t else (ctx.target or "unknown").strip()
        open_ports = data.get("open_ports") or []
        banners = data.get("banners") or {}

        services: list[NormalizedService] = []
        for port in open_ports:
            port = int(port)
            banner = str(banners.get(port) or banners.get(str(port)) or "")
            risky = _RISKY.get(port)
            service = (risky[0] if risky else "") or _KNOWN_SERVICES.get(port, "")
            services.append(
                NormalizedService(
                    port=port,
                    protocol="tcp",
                    state="open",
                    service=service,
                    product=banner[:120],
                    version="",
                )
            )

        technologies = [s.product for s in services if s.product]

        findings: list[NormalizedFinding] = []
        if services:
            port_list = ", ".join(f"{s.port}/tcp {s.service or 'open'}".strip() for s in services[:40])
            findings.append(
                NormalizedFinding(
                    title=f"Open ports discovered on {host}",
                    severity="info",
                    asset_name=host,
                    source="securaiq:discovery",
                    evidence=port_list,
                    raw={"ports": [s.__dict__ for s in services]},
                )
            )
        for s in services:
            risky = _RISKY.get(s.port)
            if not risky:
                continue
            _svc, _default_sev, msg = risky
            scope = network_scope(host)
            sev = severity_for_risky_port(s.port, scope)
            if scope == "private" and s.port in WINDOWS_LAN_PORTS:
                title = f"Windows LAN service on port {s.port}/tcp (private/lab)"
            else:
                title = f"{msg} ({s.port}/tcp"
                if s.service:
                    title += f" {s.service}"
                title += ")"
            findings.append(
                NormalizedFinding(
                    title=title[:300],
                    severity=sev,
                    asset_name=host,
                    source=f"securaiq:port-{s.port}",
                    evidence=f"{s.port}/tcp open {s.service} {s.product}".strip(),
                    raw={"port": s.port, "service": s.service, "banner": s.product, "scope": scope},
                )
            )

        return NormalizedScan(
            asset_name=host,
            asset_type="host",
            services=services,
            findings=findings,
            technologies=technologies,
            summary={
                "open_ports": len(services),
                "findings": len(findings),
                "technologies": len(technologies),
                "scanner": "securaiq",
                "profile": ctx.profile,
                "checked_ports": data.get("checked_ports") or 0,
            },
        )
