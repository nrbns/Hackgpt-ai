"""Cross-platform helpers and capability reporting."""

from __future__ import annotations

import platform
import socket
from pathlib import Path
from typing import Any

from app.config import settings


def _lan_ips() -> list[str]:
    ips: list[str] = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    # Fallback: UDP trick (no packets sent)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        if ip and not ip.startswith("127.") and ip not in ips:
            ips.insert(0, ip)
    except OSError:
        pass
    return ips[:5]


def _module_available(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def normalize_path(value: str) -> str:
    """Normalize user paths for Windows/Linux/macOS."""
    p = Path(value).expanduser()
    try:
        return str(p.resolve()) if p.exists() else str(p)
    except OSError:
        return str(p)


def platform_info() -> dict[str, Any]:
    system = platform.system()
    ips = _lan_ips()
    port = settings.port
    return {
        "os": system,
        "os_release": platform.release(),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "host": settings.host,
        "port": port,
        "lan_urls": [f"http://{ip}:{port}" for ip in ips],
        "local_url": f"http://127.0.0.1:{port}",
        "client_note": (
            "Open this UI from any browser on Windows, Linux, macOS, Android, or iOS. "
            "On phones/tablets use a LAN URL below (same Wi‑Fi). "
            "Model backends (Ollama/Hermes/Unsloth) run on the host machine — set their URLs in Settings if needed."
        ),
        "backends": {
            "ollama": {"ui": True, "server_side": True, "notes": "Works on Windows/Linux/macOS/Android (Termux) hosts"},
            "openai_compat": {"ui": True, "server_side": True, "notes": "LM Studio or any OpenAI-compatible endpoint"},
            "hermes": {
                "ui": True,
                "server_side": True,
                "notes": "Nous Hermes Agent API — sessions, tools, memory (Win/Linux/macOS host)",
            },
            "unsloth": {
                "ui": True,
                "server_side": True,
                "installed": _module_available("unsloth"),
                "notes": "GPU host recommended; not for on-device phone training",
            },
            "huggingface": {
                "ui": True,
                "server_side": True,
                "installed": _module_available("transformers"),
                "notes": "Local Transformers on host",
            },
        },
        "mobile_clients": ["Android browser", "iOS Safari", "PWA / Add to Home Screen"],
    }
