"""Select and run authorized security tools; format results for the AI."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import shutil
import socket
import ssl
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.net_assess import extract_targets, resolve_and_authorize
from app.tools.registry import (
    AUTO_LIGHT_TOOLS,
    TOOL_CATALOG,
    is_available,
    resolve_binary,
)

_CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)
_TOOL_WORD_RE = re.compile(
    r"\b(nmap|nikto|nuclei|whatweb|gobuster|ffuf|sslscan|sslyze|dig|whois|curl|"
    r"traceroute|tracert|ping|openssl|wafw00f|ports?|dns|tls|http|robots|tech|"
    r"cve_lookup|headers?(?:\s+security)?|zap|zaproxy|sqlmap|wpscan|masscan|"
    r"rustscan|openvas|greenbone|gvm|burp|acunetix|email_auth|phishing_url|suite_guide|"
    r"spf|dmarc)\b",
    re.IGNORECASE,
)
_RUN_HINT_RE = re.compile(
    r"\b(run|use|execute|launch|scan\s+with|probe\s+with|tools?\s*:)\b",
    re.IGNORECASE,
)

_COMMON_PORTS = [
    21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445,
    1433, 3306, 3389, 5432, 5985, 6379, 8080, 8443, 9200,
]

_DIR_WORDS = [
    "admin", "login", "api", "robots.txt", "sitemap.xml", ".git", ".env",
    "backup", "wp-admin", "wp-login.php", "phpmyadmin", "console", "swagger",
    "actuator", "server-status", "uploads", "static", "assets", "config",
]


def parse_tool_request(
    message: str,
    *,
    explicit: list[str] | None = None,
    auto: bool = False,
    include_heavy: bool = False,
) -> list[str]:
    """Decide which tools to run from UI list, message instructions, or auto set."""
    selected: list[str] = []

    if explicit:
        for t in explicit:
            tid = (t or "").strip().lower().replace(" ", "_")
            if tid == "tracert":
                tid = "traceroute"
            if tid in ("header", "headers", "headers_security"):
                tid = "headers_security"
            if tid in ("port", "ports"):
                tid = "ports"
            if tid in TOOL_CATALOG:
                selected.append(tid)

    # Instruction parsing: "run nmap and nikto"
    instructed = bool(_RUN_HINT_RE.search(message or "")) or bool(explicit)
    mentioned: list[str] = []
    for m in _TOOL_WORD_RE.finditer(message or ""):
        raw = m.group(1).lower()
        alias = {
            "port": "ports",
            "ports": "ports",
            "tracert": "traceroute",
            "header": "headers_security",
            "headers": "headers_security",
            "headers security": "headers_security",
            "zaproxy": "zap",
            "greenbone": "openvas",
            "gvm": "openvas",
            "burp": "suite_guide",
            "acunetix": "suite_guide",
            "spf": "email_auth",
            "dmarc": "email_auth",
        }.get(raw, raw.replace(" ", "_"))
        if alias in TOOL_CATALOG:
            mentioned.append(alias)
        elif raw == "cve_lookup" or raw.startswith("cve"):
            mentioned.append("cve_lookup")

    if instructed and mentioned:
        selected.extend(mentioned)
    elif mentioned and not auto:
        # Soft instruct: tool names alone still count when tools module is on
        selected.extend(mentioned)

    if auto and not selected:
        for tid in AUTO_LIGHT_TOOLS:
            spec = TOOL_CATALOG[tid]
            if spec.heavy and not include_heavy:
                continue
            selected.append(tid)

    # Always attach cve_lookup if CVEs present
    if _CVE_RE.search(message or "") and "cve_lookup" not in selected:
        selected.append("cve_lookup")

    # Heavy tools only when instructed / explicit / include_heavy
    out: list[str] = []
    seen: set[str] = set()
    explicit_l = {x.strip().lower() for x in (explicit or [])}
    for tid in selected:
        if tid in seen:
            continue
        spec = TOOL_CATALOG.get(tid)
        if not spec:
            continue
        if spec.heavy and not (include_heavy or tid in mentioned or tid in explicit_l):
            continue
        seen.add(tid)
        out.append(tid)
    return out[:12]


async def _run_cmd(argv: list[str], timeout: float = 25.0) -> dict[str, Any]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return {"ok": False, "error": f"timed out after {timeout:.0f}s", "output": ""}
        text = (stdout or b"").decode("utf-8", errors="replace")
        err = (stderr or b"").decode("utf-8", errors="replace")
        return {
            "ok": proc.returncode == 0 or bool(text.strip()),
            "output": (text or err)[-4500:],
            "stderr": err[-800:] if err and not text.strip() else "",
            "returncode": proc.returncode,
        }
    except FileNotFoundError:
        return {"ok": False, "error": "binary not found", "output": ""}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "output": ""}


async def _probe_port(ip: str, port: int, timeout: float = 0.35) -> bool:
    try:
        _r, w = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=timeout)
        w.close()
        try:
            await w.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


async def _tool_ports(ip: str) -> dict[str, Any]:
    flags = await asyncio.gather(*[_probe_port(ip, p) for p in _COMMON_PORTS])
    open_ports = [p for p, ok in zip(_COMMON_PORTS, flags) if ok]
    return {"ok": True, "open_ports": open_ports, "output": f"Open: {open_ports or 'none'}"}


async def _tool_dns(target: str, ip: str) -> dict[str, Any]:
    lines = [f"target={target}", f"ip={ip}"]
    try:
        infos = socket.getaddrinfo(target, None)
        addrs = sorted({i[4][0] for i in infos})
        lines.append(f"addresses={addrs}")
    except Exception as exc:
        lines.append(f"resolve_error={exc}")
    try:
        ptr, _, _ = socket.gethostbyaddr(ip)
        lines.append(f"ptr={ptr}")
    except Exception:
        lines.append("ptr=none")
    return {"ok": True, "output": "\n".join(lines)}


async def _http_get(url: str) -> tuple[httpx.Response | None, str]:
    timeout = httpx.Timeout(connect=1.0, read=4.0, write=2.0, pool=2.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=False) as client:
            r = await client.get(url, headers={"User-Agent": "HackGPT-Tools/1.0"})
            return r, ""
    except Exception as exc:
        return None, str(exc)


def _guess_base_urls(ip: str, open_ports: list[int] | None = None) -> list[str]:
    ports = open_ports or []
    urls: list[str] = []
    if 443 in ports or not ports:
        urls.append(f"https://{ip}/")
    if 8443 in ports:
        urls.append(f"https://{ip}:8443/")
    if 80 in ports or not ports:
        urls.append(f"http://{ip}/")
    if 8080 in ports:
        urls.append(f"http://{ip}:8080/")
    # de-dupe
    seen: set[str] = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out[:3]


async def _tool_http(ip: str, open_ports: list[int] | None = None) -> dict[str, Any]:
    lines = []
    for url in _guess_base_urls(ip, open_ports):
        r, err = await _http_get(url)
        if err or r is None:
            lines.append(f"{url} error={err}")
            continue
        title = ""
        m = re.search(r"<title[^>]*>(.*?)</title>", r.text[:12000], re.I | re.S)
        if m:
            title = re.sub(r"\s+", " ", m.group(1)).strip()[:120]
        interesting = {
            k: r.headers.get(k)
            for k in (
                "server", "x-powered-by", "x-frame-options", "content-security-policy",
                "strict-transport-security", "x-content-type-options", "set-cookie",
            )
            if r.headers.get(k)
        }
        lines.append(f"{url} status={r.status_code} title={title!r} headers={interesting}")
    return {"ok": bool(lines), "output": "\n".join(lines) or "no HTTP response"}


async def _tool_headers_security(ip: str, open_ports: list[int] | None = None) -> dict[str, Any]:
    checks = [
        "strict-transport-security",
        "content-security-policy",
        "x-frame-options",
        "x-content-type-options",
        "referrer-policy",
        "permissions-policy",
    ]
    lines = []
    for url in _guess_base_urls(ip, open_ports)[:2]:
        r, err = await _http_get(url)
        if r is None:
            lines.append(f"{url}: {err}")
            continue
        present = [h for h in checks if r.headers.get(h)]
        missing = [h for h in checks if h not in present]
        lines.append(f"{url}: present={present}; missing={missing}")
    return {"ok": True, "output": "\n".join(lines) or "no HTTP"}


async def _tool_tls(ip: str, open_ports: list[int] | None = None) -> dict[str, Any]:
    port = 443 if not open_ports or 443 in open_ports else (8443 if 8443 in (open_ports or []) else 443)

    def _sync() -> dict[str, str]:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((ip, port), timeout=1.5) as sock:
            with ctx.wrap_socket(sock, server_hostname=ip) as ssock:
                cert = ssock.getpeercert()
                ver = ssock.version() or ""
                if not cert:
                    return {"tls": ver, "note": "no peer cert details"}
                sub = dict(x[0] for x in cert.get("subject", ()))
                iss = dict(x[0] for x in cert.get("issuer", ()))
                return {
                    "tls": ver,
                    "cn": sub.get("commonName", ""),
                    "issuer": iss.get("commonName", ""),
                    "notAfter": cert.get("notAfter", ""),
                    "port": str(port),
                }

    try:
        data = await asyncio.to_thread(_sync)
        return {"ok": True, "output": json.dumps(data)}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "output": ""}


async def _tool_robots(ip: str, open_ports: list[int] | None = None) -> dict[str, Any]:
    lines = []
    for base in _guess_base_urls(ip, open_ports)[:2]:
        for path in ("robots.txt", "sitemap.xml"):
            url = base.rstrip("/") + "/" + path
            r, err = await _http_get(url)
            if r is None:
                lines.append(f"{url}: {err}")
            else:
                body = r.text[:800].replace("\n", " | ")
                lines.append(f"{url} [{r.status_code}]: {body}")
    return {"ok": True, "output": "\n".join(lines)}


async def _tool_tech(ip: str, open_ports: list[int] | None = None) -> dict[str, Any]:
    hints: list[str] = []
    for url in _guess_base_urls(ip, open_ports)[:2]:
        r, err = await _http_get(url)
        if r is None:
            hints.append(f"{url}: {err}")
            continue
        body = r.text[:20000].lower()
        hdr = {k.lower(): v for k, v in r.headers.items()}
        if "wordpress" in body or "wp-content" in body:
            hints.append("WordPress signals")
        if "drupal" in body:
            hints.append("Drupal signals")
        if "joomla" in body:
            hints.append("Joomla signals")
        if "react" in body or "next" in hdr.get("x-powered-by", "").lower():
            hints.append("JS framework signals")
        if "nginx" in hdr.get("server", "").lower():
            hints.append(f"Nginx: {hdr.get('server')}")
        if "apache" in hdr.get("server", "").lower():
            hints.append(f"Apache: {hdr.get('server')}")
        if "iis" in hdr.get("server", "").lower():
            hints.append(f"IIS: {hdr.get('server')}")
        if "php" in hdr.get("x-powered-by", "").lower():
            hints.append(hdr.get("x-powered-by", "PHP"))
        cookie = hdr.get("set-cookie", "")
        if "asp.net" in cookie.lower() or "asp.net" in body:
            hints.append("ASP.NET signals")
        hints.append(f"{url} server={hdr.get('server', '?')}")
    return {"ok": True, "output": "; ".join(dict.fromkeys(hints)) or "no tech hints"}


async def _tool_whois(target: str, ip: str) -> dict[str, Any]:
    # Prefer RDAP (builtin), then whois binary
    timeout = httpx.Timeout(connect=2.0, read=6.0, write=2.0, pool=2.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            r = await client.get(f"https://rdap.org/ip/{ip}")
            if r.status_code == 200:
                data = r.json()
                name = data.get("name") or data.get("handle")
                country = data.get("country")
                return {
                    "ok": True,
                    "output": json.dumps(
                        {"source": "rdap", "name": name, "country": country, "ip": ip},
                        default=str,
                    )[:2000],
                }
    except Exception:
        pass
    binary = resolve_binary(TOOL_CATALOG["whois"])
    if binary:
        # whois may need hostname; try ip
        return await _run_cmd([binary, ip], timeout=12)
    return {"ok": False, "error": "RDAP failed and whois binary missing", "output": ""}


async def _tool_cve_lookup(message: str) -> dict[str, Any]:
    cves = list(dict.fromkeys(_CVE_RE.findall(message or "")))[:3]
    if not cves:
        return {"ok": False, "error": "No CVE IDs in message", "output": ""}
    lines = []
    timeout = httpx.Timeout(connect=2.0, read=8.0, write=2.0, pool=2.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for cve in cves:
            try:
                r = await client.get(
                    "https://services.nvd.nist.gov/rest/json/cves/2.0",
                    params={"cveId": cve.upper()},
                    headers={"User-Agent": "HackGPT-Tools/1.0"},
                )
                if r.status_code != 200:
                    lines.append(f"{cve}: HTTP {r.status_code}")
                    continue
                vulns = (r.json().get("vulnerabilities") or [])
                if not vulns:
                    lines.append(f"{cve}: not found")
                    continue
                cve_obj = vulns[0].get("cve") or {}
                desc = next(
                    (d.get("value") for d in (cve_obj.get("descriptions") or []) if d.get("lang") == "en"),
                    "",
                )
                metrics = cve_obj.get("metrics") or {}
                score = ""
                for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
                    arr = metrics.get(key) or []
                    if arr:
                        score = str((arr[0].get("cvssData") or {}).get("baseScore", ""))
                        break
                lines.append(f"{cve.upper()} CVSS={score} — {(desc or '')[:500]}")
            except Exception as exc:
                lines.append(f"{cve}: {exc}")
    return {"ok": True, "output": "\n".join(lines)}


_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
_DOMAIN_RE = re.compile(r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b", re.I)


async def _tool_email_auth(target: str) -> dict[str, Any]:
    domain = target.strip().lower()
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", domain):
        return {
            "ok": False,
            "error": "email_auth needs a domain (e.g. example.com), not an IP",
            "output": "",
        }
    domain = domain.removeprefix("http://").removeprefix("https://").split("/")[0]
    lines = [f"domain={domain}"]
    dig = resolve_binary(TOOL_CATALOG["dig"]) if "dig" in TOOL_CATALOG else None
    for name, qname in (("SPF", domain), ("DMARC", f"_dmarc.{domain}")):
        if dig:
            res = await _run_cmd([dig, "+short", "TXT", qname], timeout=8)
            lines.append(f"{name} TXT: {(res.get('output') or res.get('error') or 'none').strip()[:500]}")
        else:
            nslookup = shutil.which("nslookup")
            if nslookup:
                res = await _run_cmd([nslookup, "-type=TXT", qname], timeout=10)
                lines.append(f"{name}:\n{(res.get('output') or '')[:600]}")
            else:
                lines.append(f"{name}: install dig/nslookup for TXT lookups (`nslookup -type=TXT {qname}`)")
    lines.append("Awareness: SPF fail + DMARC p=quarantine/reject reduces spoofed phishing.")
    return {"ok": True, "output": "\n".join(lines)}


async def _tool_phishing_url(message: str) -> dict[str, Any]:
    urls = _URL_RE.findall(message or "")[:5]
    if not urls:
        # try bare domains as example
        return {
            "ok": True,
            "output": (
                "No URL found. Paste a sample lure URL for awareness review.\n"
                "Teach users: hover links, check domain brand mismatch, unexpected MFA prompts, "
                "urgency/fear language, lookalike domains (rn→m), and report-don't-click."
            ),
        }
    findings = []
    for url in urls:
        flags = []
        host = re.sub(r"^https?://", "", url, flags=re.I).split("/")[0].lower()
        if re.search(r"\d{1,3}(\.\d{1,3}){3}", host):
            flags.append("raw-IP host (common in phish)")
        if "@" in url:
            flags.append("credential-in-URL / @ trick")
        if host.count(".") >= 3:
            flags.append("deep subdomain (lookalike risk)")
        for brand in ("microsoft", "google", "apple", "paypal", "okta", "login", "secure", "account"):
            if brand in host and not host.endswith(f"{brand}.com") and brand not in host.split(".")[0:1]:
                flags.append(f"brand keyword in host ({brand})")
        if any(x in url.lower() for x in ("%2f", "..", "redirect", "url=")):
            flags.append("redirect / encoding pattern")
        findings.append(f"{url}\n  host={host}\n  flags={flags or ['none — still verify via SOC process']}")
    findings.append(
        "Training note: label simulations clearly in real programs; measure report-rate not shame."
    )
    return {"ok": True, "output": "\n".join(findings)}


async def _tool_suite_guide() -> dict[str, Any]:
    zap = resolve_binary(TOOL_CATALOG["zap"]) if "zap" in TOOL_CATALOG else None
    gvm = resolve_binary(TOOL_CATALOG["openvas"]) if "openvas" in TOOL_CATALOG else None
    nuclei = resolve_binary(TOOL_CATALOG["nuclei"]) if "nuclei" in TOOL_CATALOG else None
    text = f"""Authorized lab / engagement tool playbooks

## Burp Suite (PortSwigger)
- Community/Pro GUI: proxy 127.0.0.1:8080, intercept, repeater, intruder (lab apps).
- Scope only in-scope hosts. Export sitemap → report.
- Equivalent FOSS: OWASP ZAP {'READY: ' + zap if zap else '(install zaproxy / zap.sh)'}.

## Acunetix (licensed DAST)
- Point at lab/staging URL with credentials in scope.
- API: set ACUNETIX_URL + API key in env if you automate; otherwise use UI scans.
- FOSS stand-ins: ZAP baseline + Nuclei {'READY' if nuclei else '(install nuclei)'}.

## Greenbone / OpenVAS (GVM)
- Install Greenbone Community Edition; scan RFC1918 / VPN lab ranges only.
- CLI: gvm-cli / gvm-script {'READY: ' + gvm if gvm else '(not on PATH — install GVM)'}.
- Feed sync required before useful NVTs.

## Quick authorized commands
```bash
# ZAP baseline
zap-baseline.py -t http://192.168.56.101/
# Greenbone: create target + task in UI, or gvm-cli TLS
# Nuclei
nuclei -u http://192.168.56.101/ -severity critical,high
# Nmap service
nmap -sV -sC 192.168.56.101
```

Always: written scope, rate limits, detection notes, remediation owners.
"""
    return {"ok": True, "output": text}


async def _run_external(tool_id: str, target: str, ip: str, open_ports: list[int] | None) -> dict[str, Any]:
    spec = TOOL_CATALOG[tool_id]
    binary = resolve_binary(spec)
    if not binary:
        return {"ok": False, "error": f"{tool_id} not installed (PATH)", "output": ""}

    base_http = _guess_base_urls(ip, open_ports)[0] if _guess_base_urls(ip, open_ports) else f"http://{ip}/"

    if tool_id == "nmap":
        return await _run_cmd(
            [binary, "-Pn", "-sT", "--top-ports", "40", "-T4", "--open", "--host-timeout", "18s", ip],
            timeout=28,
        )
    if tool_id == "nikto":
        return await _run_cmd([binary, "-h", base_http, "-maxtime", "20s"], timeout=30)
    if tool_id == "nuclei":
        return await _run_cmd(
            [binary, "-u", base_http, "-severity", "critical,high,medium", "-silent", "-timeout", "5", "-rate-limit", "50"],
            timeout=35,
        )
    if tool_id == "whatweb":
        return await _run_cmd([binary, "-a", "1", base_http], timeout=20)
    if tool_id == "dig":
        return await _run_cmd([binary, "+short", "A", target], timeout=10)
    if tool_id == "curl":
        return await _run_cmd([binary, "-sI", "-L", "--max-time", "8", base_http], timeout=12)
    if tool_id == "sslscan":
        hostport = f"{ip}:443" if not open_ports or 443 in open_ports else f"{ip}:8443"
        return await _run_cmd([binary, "--no-colour", hostport], timeout=25)
    if tool_id == "sslyze":
        return await _run_cmd([binary, f"{ip}:443"], timeout=30)
    if tool_id == "gobuster":
        wordlist = _ensure_mini_wordlist()
        return await _run_cmd(
            [binary, "dir", "-u", base_http, "-w", str(wordlist), "-q", "-t", "20", "--timeout", "5s"],
            timeout=30,
        )
    if tool_id == "ffuf":
        wordlist = _ensure_mini_wordlist()
        return await _run_cmd(
            [binary, "-u", base_http.rstrip("/") + "/FUZZ", "-w", str(wordlist), "-mc", "200,204,301,302,403", "-t", "10", "-timeout", "5"],
            timeout=30,
        )
    if tool_id == "traceroute":
        # Windows tracert vs unix traceroute
        if binary.lower().endswith("tracert.exe") or binary.lower().endswith("tracert"):
            return await _run_cmd([binary, "-d", "-h", "8", ip], timeout=25)
        return await _run_cmd([binary, "-n", "-m", "8", ip], timeout=25)
    if tool_id == "ping":
        # Windows: -n count; Unix: -c count
        import sys
        if sys.platform.startswith("win"):
            return await _run_cmd([binary, "-n", "2", "-w", "1000", ip], timeout=8)
        return await _run_cmd([binary, "-c", "2", "-W", "1", ip], timeout=8)
    if tool_id == "openssl":
        # echo | openssl s_client -connect
        try:
            proc = await asyncio.create_subprocess_exec(
                binary, "s_client", "-connect", f"{ip}:443", "-servername", target,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(input=b"Q\n"), timeout=12)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return {"ok": False, "error": "timed out", "output": ""}
            text = (stdout or b"").decode("utf-8", errors="replace")
            # keep certificate / protocol lines
            keep = [ln for ln in text.splitlines() if any(k in ln for k in ("Protocol", "Cipher", "subject=", "issuer=", "Verify"))]
            return {"ok": True, "output": "\n".join(keep)[:3000] or text[:2000]}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "output": ""}
    if tool_id == "wafw00f":
        return await _run_cmd([binary, base_http], timeout=20)
    if tool_id == "zap":
        # Prefer zap-baseline.py alongside zap if present
        baseline = shutil.which("zap-baseline.py") or shutil.which("zap-baseline")
        if baseline:
            return await _run_cmd([baseline, "-t", base_http, "-I"], timeout=50)
        return await _run_cmd(
            [binary, "-cmd", "-quickurl", base_http, "-quickprogress"],
            timeout=50,
        )
    if tool_id == "sqlmap":
        return await _run_cmd(
            [binary, "-u", base_http, "--batch", "--level=1", "--risk=1", "--timeout=8", "--smart"],
            timeout=40,
        )
    if tool_id == "wpscan":
        return await _run_cmd([binary, "--url", base_http, "--no-update", "-e", "vp,vt"], timeout=40)
    if tool_id == "masscan":
        return await _run_cmd(
            [binary, ip, "-p1-1024,3306,3389,8080,8443", "--rate", "500", "--wait", "0"],
            timeout=25,
        )
    if tool_id == "rustscan":
        return await _run_cmd([binary, "-a", ip, "--ulimit", "5000", "-g"], timeout=25)
    if tool_id == "openvas":
        # gvm-cli / openvas — status oriented; full scans are async in GVM
        if binary.endswith("gvm-cli") or binary.endswith("gvm-cli.exe"):
            return await _run_cmd([binary, "--version"], timeout=10)
        return await _run_cmd([binary, "--version"], timeout=10)

    return {"ok": False, "error": f"no runner for {tool_id}", "output": ""}


def _ensure_mini_wordlist() -> Path:
    path = Path(settings.chroma_persist_dir).resolve().parent / "wordlists" / "hackgpt-mini.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("\n".join(_DIR_WORDS) + "\n", encoding="utf-8")
    return path


async def run_security_tools(
    message: str,
    *,
    target: str | None = None,
    tools: list[str] | None = None,
    authorized: bool = False,
    allow_public: bool = False,
    auto: bool = False,
    include_heavy: bool = False,
) -> dict[str, Any]:
    if not settings.local_tools_enabled:
        return {"ok": False, "error": "Local tools disabled", "runs": []}

    tool_ids = parse_tool_request(
        message,
        explicit=tools,
        auto=auto,
        include_heavy=include_heavy,
    )
    if not tool_ids:
        return {"ok": False, "error": "No tools selected", "runs": []}

    targets = extract_targets(message, target)
    needs_target = any(TOOL_CATALOG[t].needs_target for t in tool_ids if t in TOOL_CATALOG)
    if needs_target and not targets:
        # Allow CVE-only tools
        non_target = [t for t in tool_ids if t in TOOL_CATALOG and not TOOL_CATALOG[t].needs_target]
        if non_target:
            tool_ids = non_target
            targets = []
        else:
            return {
                "ok": False,
                "error": "No target IP/host — set Target IP or include an address in the message",
                "runs": [],
                "requested": tool_ids,
            }

    runs: list[dict[str, Any]] = []
    open_ports: list[int] = []

    # Host authorization (first target)
    meta = None
    ip = ""
    host = ""
    if targets:
        host = targets[0]
        meta = resolve_and_authorize(host, authorized=authorized, allow_public=allow_public)
        if not meta.get("ok"):
            return {
                "ok": False,
                "error": meta.get("error") or "Target not authorized",
                "runs": [],
                "requested": tool_ids,
                "target": host,
            }
        ip = meta["ip"]

    # Prefer ports first when present
    ordered = sorted(tool_ids, key=lambda t: 0 if t == "ports" else 1)

    for tid in ordered:
        spec = TOOL_CATALOG.get(tid)
        if not spec:
            continue
        entry: dict[str, Any] = {"tool": tid, "name": spec.name, "kind": spec.kind}
        try:
            if tid == "cve_lookup":
                result = await _tool_cve_lookup(message)
            elif tid == "phishing_url":
                result = await _tool_phishing_url(message)
            elif tid == "suite_guide":
                result = await _tool_suite_guide()
            elif not ip and tid == "email_auth":
                # allow domain in target field even if resolve failed earlier — handled below
                result = {"ok": False, "error": "no target", "output": ""}
            elif not ip:
                result = {"ok": False, "error": "no target", "output": ""}
            elif tid == "ports":
                result = await _tool_ports(ip)
                open_ports = result.get("open_ports") or open_ports
            elif tid == "dns":
                result = await _tool_dns(host, ip)
            elif tid == "http":
                result = await _tool_http(ip, open_ports)
            elif tid == "headers_security":
                result = await _tool_headers_security(ip, open_ports)
            elif tid == "tls":
                result = await _tool_tls(ip, open_ports)
            elif tid == "robots":
                result = await _tool_robots(ip, open_ports)
            elif tid == "tech":
                result = await _tool_tech(ip, open_ports)
            elif tid == "whois":
                result = await _tool_whois(host, ip)
            elif tid == "email_auth":
                # Prefer hostname/domain if not an IP
                domain = host if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host) else host
                result = await _tool_email_auth(domain)
            elif spec.kind == "external":
                if not is_available(tid):
                    result = {"ok": False, "error": "not installed on PATH", "output": ""}
                else:
                    result = await _run_external(tid, host, ip, open_ports)
            else:
                result = {"ok": False, "error": "unknown tool", "output": ""}
        except Exception as exc:
            result = {"ok": False, "error": str(exc), "output": ""}

        entry.update(result)
        runs.append(entry)

    ok_any = any(r.get("ok") for r in runs)
    return {
        "ok": ok_any,
        "target": host or None,
        "ip": ip or None,
        "private": (meta or {}).get("private"),
        "requested": tool_ids,
        "open_ports": open_ports,
        "runs": runs,
        "fingerprint": hashlib.sha1(f"{host}:{ip}:{','.join(tool_ids)}".encode()).hexdigest()[:10],
    }


def format_tools_context(payload: dict[str, Any]) -> str:
    runs = payload.get("runs") or []
    if not runs:
        err = payload.get("error") or "No tool output"
        return (
            "## Local security tools\n"
            f"No runs ({err}). Built-in tools work without installs; "
            "install nmap/nuclei/nikto/etc. on PATH for deeper scans.\n"
            "Ask e.g. `run nmap and http on 192.168.56.101` (authorized lab only)."
        )

    lines = [
        "## Local security tools output (authorized / lab scope)",
        f"Target: `{payload.get('target')}` → `{payload.get('ip')}` · private={payload.get('private')}",
        f"Requested: {', '.join(payload.get('requested') or [])}",
        "Use this evidence for findings, CVE mapping, verify commands, detection, and remediation.",
        "",
    ]
    for r in runs:
        status = "OK" if r.get("ok") else "FAIL"
        lines.append(f"### {r.get('name', r.get('tool'))} [{status}]")
        if r.get("error"):
            lines.append(f"- Error: {r['error']}")
        if r.get("open_ports") is not None:
            lines.append(f"- Open ports: {r['open_ports']}")
        out = (r.get("output") or "").strip()
        if out:
            lines.append("```")
            lines.append(out[-3500:])
            lines.append("```")
        lines.append("")
    return "\n".join(lines)
