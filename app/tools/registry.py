"""Security tool catalog: builtins (always) + external binaries (when installed)."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Literal


Kind = Literal["builtin", "external"]


@dataclass(frozen=True)
class ToolSpec:
    id: str
    name: str
    kind: Kind
    description: str
    binaries: tuple[str, ...] = ()  # PATH names for external tools
    needs_target: bool = True
    heavy: bool = False  # opt-in / instruct-only by default
    category: str = "recon"


TOOL_CATALOG: dict[str, ToolSpec] = {
    # --- Built-ins (always available; no install) ---
    "ports": ToolSpec(
        "ports", "Port probe", "builtin",
        "Fast TCP probe of common lab ports",
        category="recon",
    ),
    "http": ToolSpec(
        "http", "HTTP fingerprint", "builtin",
        "Fetch headers, status, title, security headers",
        category="web",
    ),
    "tls": ToolSpec(
        "tls", "TLS cert", "builtin",
        "TLS version + certificate summary",
        category="web",
    ),
    "dns": ToolSpec(
        "dns", "DNS lookup", "builtin",
        "A/AAAA resolve + reverse PTR",
        category="recon",
    ),
    "whois": ToolSpec(
        "whois", "RDAP / WHOIS", "builtin",
        "RDAP query (fallback to whois binary if present)",
        binaries=("whois",),
        category="recon",
    ),
    "robots": ToolSpec(
        "robots", "robots.txt / sitemap", "builtin",
        "Fetch robots.txt and sitemap.xml hints",
        category="web",
    ),
    "tech": ToolSpec(
        "tech", "Tech fingerprint", "builtin",
        "Lightweight stack hints from headers/body",
        category="web",
    ),
    "cve_lookup": ToolSpec(
        "cve_lookup", "CVE lookup", "builtin",
        "Pull NVD detail for CVE IDs mentioned in the message",
        needs_target=False,
        category="intel",
    ),
    "headers_security": ToolSpec(
        "headers_security", "Security headers check", "builtin",
        "Score common HTTP security headers",
        category="web",
    ),
    "email_auth": ToolSpec(
        "email_auth", "Email auth (SPF/DMARC)", "builtin",
        "DNS TXT lookup for SPF and DMARC (awareness / blue team)",
        needs_target=True,
        category="awareness",
    ),
    "phishing_url": ToolSpec(
        "phishing_url", "Phishing URL review", "builtin",
        "Heuristic review of URLs in the message for awareness training",
        needs_target=False,
        category="awareness",
    ),
    "suite_guide": ToolSpec(
        "suite_guide", "Burp / Acunetix / Greenbone guide", "builtin",
        "How to run Burp Suite, Acunetix, Greenbone/OpenVAS, ZAP in authorized labs",
        needs_target=False,
        category="intel",
    ),
    # --- External (detected via PATH) ---
    "nmap": ToolSpec(
        "nmap", "Nmap", "external",
        "Service/version scan (top ports)",
        binaries=("nmap",),
        category="recon",
    ),
    "nikto": ToolSpec(
        "nikto", "Nikto", "external",
        "Web server vulnerability scan",
        binaries=("nikto", "nikto.pl"),
        heavy=True,
        category="web",
    ),
    "nuclei": ToolSpec(
        "nuclei", "Nuclei", "external",
        "Template-based vuln scan (severity capped)",
        binaries=("nuclei",),
        heavy=True,
        category="vuln",
    ),
    "zap": ToolSpec(
        "zap", "OWASP ZAP", "external",
        "Baseline web scan (open-source Burp/Acunetix-class coverage)",
        binaries=("zap.sh", "zap", "zaproxy"),
        heavy=True,
        category="web",
    ),
    "sqlmap": ToolSpec(
        "sqlmap", "sqlmap", "external",
        "SQL injection test (lab targets only)",
        binaries=("sqlmap", "sqlmap.py"),
        heavy=True,
        category="web",
    ),
    "wpscan": ToolSpec(
        "wpscan", "WPScan", "external",
        "WordPress vulnerability scan",
        binaries=("wpscan",),
        heavy=True,
        category="web",
    ),
    "masscan": ToolSpec(
        "masscan", "Masscan", "external",
        "Fast port sweep (rate-limited, lab host only)",
        binaries=("masscan",),
        heavy=True,
        category="recon",
    ),
    "rustscan": ToolSpec(
        "rustscan", "RustScan", "external",
        "Fast port discovery then nmap scripts",
        binaries=("rustscan",),
        category="recon",
    ),
    "openvas": ToolSpec(
        "openvas", "Greenbone / OpenVAS", "external",
        "GVM/OpenVAS CLI probe when gvm-cli/openvas installed",
        binaries=("gvm-cli", "openvas", "gvm-script"),
        heavy=True,
        category="vuln",
    ),
    "whatweb": ToolSpec(
        "whatweb", "WhatWeb", "external",
        "Web technology fingerprinting",
        binaries=("whatweb",),
        category="web",
    ),
    "dig": ToolSpec(
        "dig", "dig", "external",
        "DNS dig ANY/A/MX/TXT (when available)",
        binaries=("dig",),
        category="recon",
    ),
    "curl": ToolSpec(
        "curl", "curl", "external",
        "HTTP request with response headers",
        binaries=("curl",),
        category="web",
    ),
    "sslscan": ToolSpec(
        "sslscan", "sslscan", "external",
        "SSL/TLS cipher and protocol scan",
        binaries=("sslscan",),
        category="web",
    ),
    "sslyze": ToolSpec(
        "sslyze", "SSLyze", "external",
        "Python SSL/TLS analyzer",
        binaries=("sslyze",),
        heavy=True,
        category="web",
    ),
    "gobuster": ToolSpec(
        "gobuster", "Gobuster", "external",
        "Directory brute (small built-in wordlist)",
        binaries=("gobuster",),
        heavy=True,
        category="web",
    ),
    "ffuf": ToolSpec(
        "ffuf", "ffuf", "external",
        "Web fuzzer (small wordlist, rate-limited)",
        binaries=("ffuf",),
        heavy=True,
        category="web",
    ),
    "traceroute": ToolSpec(
        "traceroute", "Traceroute", "external",
        "Path trace (tracert on Windows)",
        binaries=("traceroute", "tracert"),
        category="recon",
    ),
    "ping": ToolSpec(
        "ping", "Ping", "external",
        "ICMP reachability check",
        binaries=("ping",),
        category="recon",
    ),
    "openssl": ToolSpec(
        "openssl", "OpenSSL s_client", "external",
        "TLS handshake peek",
        binaries=("openssl",),
        category="web",
    ),
    "wafw00f": ToolSpec(
        "wafw00f", "wafw00f", "external",
        "WAF detection",
        binaries=("wafw00f",),
        category="web",
    ),
}


# Default auto set for assess / when tools enabled with a target
AUTO_LIGHT_TOOLS = (
    "dns",
    "ports",
    "http",
    "tls",
    "tech",
    "headers_security",
    "robots",
    "email_auth",
    "nmap",
    "dig",
    "curl",
    "whatweb",
    "sslscan",
    "ping",
    "rustscan",
)


def resolve_binary(spec: ToolSpec) -> str | None:
    if spec.kind == "builtin":
        return None
    for name in spec.binaries:
        path = shutil.which(name)
        if path:
            return path
    return None


def is_available(tool_id: str) -> bool:
    spec = TOOL_CATALOG.get(tool_id)
    if not spec:
        return False
    if spec.kind == "builtin":
        return True
    return resolve_binary(spec) is not None


def list_tools_status() -> dict:
    tools = []
    available = 0
    for tid, spec in TOOL_CATALOG.items():
        avail = is_available(tid)
        if avail:
            available += 1
        tools.append(
            {
                "id": tid,
                "name": spec.name,
                "kind": spec.kind,
                "description": spec.description,
                "available": avail,
                "heavy": spec.heavy,
                "needs_target": spec.needs_target,
                "category": spec.category,
                "binary": resolve_binary(spec) if spec.kind == "external" else "builtin",
            }
        )
    return {
        "count": len(tools),
        "available_count": available,
        "tools": tools,
        "auto_light": list(AUTO_LIGHT_TOOLS),
    }
