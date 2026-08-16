"""Shared scanner constants (avoid circular imports with nmap/builtin)."""

from __future__ import annotations

import re

HOST_OR_IP = re.compile(
    r"^(?:"
    r"(?:\d{1,3}\.){3}\d{1,3}"
    r"|(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(?:\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*\.?"
    r")$"
)

# Ports that warrant a finding (not every open port = vuln)
RISKY_PORTS = {
    21: ("ftp", "medium", "FTP service exposed"),
    23: ("telnet", "high", "Telnet (cleartext) exposed"),
    25: ("smtp", "low", "SMTP service exposed"),
    135: ("msrpc", "medium", "MSRPC exposed"),
    139: ("netbios", "medium", "NetBIOS exposed"),
    445: ("smb", "high", "SMB exposed"),
    1433: ("mssql", "high", "MSSQL exposed"),
    3306: ("mysql", "high", "MySQL exposed"),
    3389: ("rdp", "high", "RDP exposed"),
    5432: ("postgres", "high", "PostgreSQL exposed"),
    5900: ("vnc", "high", "VNC exposed"),
    6379: ("redis", "critical", "Redis exposed"),
    27017: ("mongodb", "high", "MongoDB exposed"),
}
