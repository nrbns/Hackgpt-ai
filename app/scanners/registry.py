"""Scanner registry — all engine adapters: securaiq, nmap, nuclei, zap."""

from __future__ import annotations

from app.scanners.base import Scanner
from app.scanners.builtin import BuiltinScanner
from app.scanners.nmap import NmapScanner
from app.scanners.nuclei import NucleiScanner
from app.scanners.zap import ZapScanner

_SCANNERS: dict[str, Scanner] = {
    "securaiq": BuiltinScanner(),
    "nmap": NmapScanner(),
    "nuclei": NucleiScanner(),
    "zap": ZapScanner(),
}

ENGINE_ENABLED = frozenset({"securaiq", "nmap", "nuclei", "zap"})


def get_scanner(scanner_id: str) -> Scanner:
    sid = (scanner_id or "").strip().lower()
    if sid not in _SCANNERS:
        raise KeyError(f"Unknown scanner '{scanner_id}'. Known: {sorted(_SCANNERS)}")
    return _SCANNERS[sid]


def list_scanners() -> list[dict]:
    out = []
    for sid, sc in _SCANNERS.items():
        ok, detail = sc.available()
        out.append(
            {
                "id": sid,
                "name": sc.name,
                "profiles": list(sc.profiles),
                "available": ok,
                "detail": detail,
                "engine_enabled": sid in ENGINE_ENABLED,
            }
        )
    return out
