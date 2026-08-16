"""Exposure-aware finding policy — severity by network scope + port dedupe keys.

Used by live tools persist and scan-engine normalizers so one RFC1918 Windows
host does not create 9× medium/high findings for the same SMB/RPC ports.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any

# Common Windows LAN listeners — expected on host-only / lab gateways (.1), not
# automatically "ransomware critical" when the target is private.
WINDOWS_LAN_PORTS = frozenset({135, 139, 445})

RISKY_PORT_NOTES: dict[int, str] = {
    21: "FTP (unencrypted; prefer SFTP/FTPS or disable)",
    23: "Telnet (unencrypted remote shell; disable, use SSH)",
    135: "MSRPC (Windows RPC; should not face untrusted networks)",
    139: "NetBIOS (should not face untrusted networks)",
    445: "SMB (high risk when internet-facing; common on private Windows LANs)",
    3389: "RDP (brute-force/ransomware target; put behind VPN + MFA)",
    5900: "VNC (often weak/no auth; put behind VPN)",
    6379: "Redis (frequently unauthenticated by default)",
    9200: "Elasticsearch (frequently unauthenticated by default)",
    27017: "MongoDB (frequently unauthenticated by default)",
    3306: "MySQL (should not face untrusted networks)",
    5432: "PostgreSQL (should not face untrusted networks)",
}

HIGH_RISK_PORTS = frozenset({445, 3389, 23, 21, 6379, 27017, 9200})

_PORT_IN_TEXT = re.compile(r"\bport\s+(\d+)/tcp\b", re.I)


def host_token(target: str) -> str:
    raw = (target or "").strip().lower()
    if not raw:
        return ""
    token = raw.split()[0].strip("()[],")
    if token.endswith(":") and token.count(":") == 1:
        token = token[:-1]
    # Strip URL scheme / path
    token = re.sub(r"^https?://", "", token, flags=re.I).split("/")[0].split(":")[0]
    return token


def network_scope(target: str, ip: str | None = None) -> str:
    """Classify exposure: loopback | private | public | unknown."""
    for candidate in (host_token(ip or ""), host_token(target)):
        if not candidate:
            continue
        if candidate in {"localhost", "::1"} or candidate.startswith("127."):
            return "loopback"
        try:
            obj = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if obj.is_loopback:
            return "loopback"
        if obj.is_private or obj.is_link_local:
            return "private"
        if obj.is_global:
            return "public"
    host = host_token(target)
    if host in {"localhost"} or host.endswith(".local") or host.endswith(".lan"):
        return "private"
    return "unknown"


def extract_port(text: str) -> int | None:
    m = _PORT_IN_TEXT.search(text or "")
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def port_dedupe_key(asset: str, port: int) -> tuple[str, int]:
    return (host_token(asset) or (asset or "").strip().lower(), int(port))


def severity_for_risky_port(port: int, scope: str) -> str:
    """Map port + scope → severity (lab-private Windows services → info)."""
    if scope == "loopback":
        return "info"
    if scope == "private" and port in WINDOWS_LAN_PORTS:
        return "info"
    if scope == "private":
        return "low" if port not in HIGH_RISK_PORTS else "medium"
    if scope == "public":
        return "high" if port in HIGH_RISK_PORTS else "medium"
    # unknown — conservative middle
    return "medium" if port in HIGH_RISK_PORTS else "low"


def risky_port_finding(
    port: int,
    *,
    target: str,
    source: str,
    ip: str | None = None,
) -> dict[str, Any]:
    """Canonical finding for a risky open port (single source of truth for title/sev)."""
    note = RISKY_PORT_NOTES.get(port, "Potentially sensitive service")
    scope = network_scope(target, ip)
    sev = severity_for_risky_port(port, scope)

    if scope == "loopback":
        title = f"Local listener on port {port}/tcp (loopback only)"
        guidance = (
            f"Port {port}/tcp is open on loopback ({target}). Not remotely reachable. "
            f"Confirm the service is needed. Note: {note}"
        )
    elif scope == "private" and port in WINDOWS_LAN_PORTS:
        title = f"Windows LAN service on port {port}/tcp (private/lab)"
        guidance = (
            f"Port {port}/tcp ({note}) is common on Windows hosts inside private networks "
            f"(including VirtualBox host-only gateways like x.x.x.1). Not internet-facing by "
            f"itself. Escalate only if this host should not expose SMB/RPC on the LAN, or if "
            f"you meant to scan a different lab VM IP."
        )
    elif scope == "private":
        title = f"LAN-reachable service on port {port}/tcp"
        guidance = (
            f"Port {port}/tcp is open on a private/lab host ({target}). Risk is lateral "
            f"movement inside the network unless NAT/port-forward exists. Note: {note}"
        )
    else:
        title = f"Exposed risky service on port {port}/tcp"
        guidance = (
            f"Port {port}/tcp appears reachable on {target}. Confirm it is not internet-facing; "
            f"if it is, disable, put behind VPN, or harden immediately. Note: {note}"
        )

    return {
        "title": title,
        "severity": sev,
        "asset_name": str(target)[:200],
        "source": source,
        "raw": {
            "port": port,
            "note": note,
            "scope": scope,
            "guidance": guidance,
            "ip": ip,
            "dedupe": "risky_port",
        },
    }


def reclassify_stored_risky_ports(user_id: str) -> dict[str, Any]:
    """Fix legacy High SMB/RPC findings on private hosts to match exposure policy."""
    import json

    from app.db import get_conn, now, row_to_dict

    c = get_conn()
    rows = c.execute(
        "SELECT id, title, severity, asset_name, raw_json FROM vulnerabilities WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    updated = 0
    for row in rows:
        d = row_to_dict(row) or {}
        raw_s = d.get("raw_json") or "{}"
        try:
            raw = json.loads(raw_s) if isinstance(raw_s, str) else (raw_s or {})
        except Exception:
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        port = raw.get("port")
        if port is None:
            port = extract_port(d.get("title") or "")
        if port is None:
            # Heuristic from legacy titles
            title_l = (d.get("title") or "").lower()
            if "445" in title_l or "smb" in title_l:
                port = 445
            elif "135" in title_l or "msrpc" in title_l or "rpc" in title_l:
                port = 135
            elif "139" in title_l or "netbios" in title_l:
                port = 139
        try:
            port_i = int(port) if port is not None else None
        except (TypeError, ValueError):
            port_i = None
        if port_i is None or port_i not in WINDOWS_LAN_PORTS:
            continue
        asset = d.get("asset_name") or raw.get("ip") or ""
        scope = network_scope(str(asset), raw.get("ip"))
        if scope not in {"private", "loopback"}:
            continue
        canon = risky_port_finding(port_i, target=str(asset), source=d.get("source") or "reclassify", ip=raw.get("ip"))
        new_sev = canon["severity"]
        new_title = canon["title"]
        if (d.get("severity") or "").lower() == new_sev and (d.get("title") or "") == new_title:
            continue
        raw.update(canon.get("raw") or {})
        c.execute(
            "UPDATE vulnerabilities SET severity = ?, title = ?, raw_json = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (new_sev, new_title, json.dumps(raw), now(), d["id"], user_id),
        )
        updated += 1
    if updated:
        c.commit()
    return {"updated": updated}
