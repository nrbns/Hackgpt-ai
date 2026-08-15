#!/usr/bin/env python3
"""Verify connector status endpoints — safe against unconfigured vendors.

Usage:
  python scripts/connector_verify.py
  python scripts/connector_verify.py --base http://127.0.0.1:8080 --sync
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any

ENDPOINTS = [
    ("GET", "/api/integrations/catalog"),
    ("GET", "/api/wazuh/status"),
    ("GET", "/api/openaudit/status"),
    ("GET", "/api/xdr/status"),
    ("GET", "/api/hardeningkitty/status"),
    ("GET", "/api/thehive/status"),
    ("GET", "/api/cloud/status"),
    ("GET", "/api/gap/evidence-queue"),
]

SYNC_ENDPOINTS = [
    "/api/wazuh/sync",
    "/api/openaudit/sync",
    "/api/xdr/sync",
    "/api/thehive/sync",
    "/api/cloud/sync",
]


def _req(base: str, method: str, path: str, timeout: float = 20.0) -> tuple[int, Any]:
    url = base.rstrip("/") + path
    r = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                data = {"raw": body[:200]}
            return int(resp.status), data
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {"raw": body[:200]}
        return int(exc.code), data
    except Exception as exc:  # noqa: BLE001
        return 0, {"error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description="SecuraIQ connector verification harness")
    parser.add_argument("--base", default="http://127.0.0.1:8080")
    parser.add_argument("--sync", action="store_true", help="Also POST sync for configured connectors")
    args = parser.parse_args()

    fails = 0
    print(f"Base: {args.base}")
    for method, path in ENDPOINTS:
        code, data = _req(args.base, method, path)
        ok = 200 <= code < 300
        if not ok or code >= 500:
            fails += 1
        summary = ""
        if isinstance(data, dict):
            if "configured" in data:
                summary = f"configured={data.get('configured')}"
            elif "configured_count" in data:
                summary = f"configured_count={data.get('configured_count')}"
            elif "count" in data and "items" in data:
                summary = f"queue={data.get('count')}"
            elif "vendors" in data:
                summary = f"vendors={len(data.get('vendors') or {})}"
            elif "groups" in data:
                summary = "catalog"
            elif "count" in data:
                summary = f"count={data.get('count')}"
            elif data.get("error"):
                summary = str(data.get("error"))[:80]
        mark = "OK" if ok else "FAIL"
        print(f"  [{mark}] {method} {path} -> {code} {summary}")

    if args.sync:
        print("-- sync (only if configured) --")
        for path in SYNC_ENDPOINTS:
            st_path = path.replace("/sync", "/status")
            _code, st = _req(args.base, "GET", st_path)
            configured = False
            if isinstance(st, dict):
                configured = bool(st.get("configured") or st.get("configured_count"))
            if not configured:
                print(f"  [skip] POST {path} (not configured)")
                continue
            sc, _data = _req(args.base, "POST", path)
            ok = 200 <= sc < 300
            if not ok:
                fails += 1
            print(f"  [{'OK' if ok else 'FAIL'}] POST {path} -> {sc}")

    print(f"Result: {'PASS' if fails == 0 else f'FAIL ({fails})'}")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
