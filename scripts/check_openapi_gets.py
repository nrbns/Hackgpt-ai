"""Audit every safe, parameter-free GET endpoint exposed by OpenAPI.

Streaming endpoints and routes requiring path/query parameters are skipped.
Run with the API server active:
    .venv/Scripts/python scripts/check_openapi_gets.py
"""

from __future__ import annotations

import sys

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080").rstrip("/")
SKIP = {
    "/api/realtime",  # Server-sent event stream does not terminate.
    "/api/auth/oidc/login",  # Redirects or 400 when auth/OIDC disabled
    "/api/auth/oidc/callback",  # Requires valid OIDC code + state
}
# Optional features: 503 "disabled" is healthy for default lab installs.
OPTIONAL_DISABLED_PREFIXES = ("/scim/",)


def main() -> int:
    with httpx.Client(timeout=45.0, follow_redirects=True) as client:
        schema_response = client.get(f"{BASE}/openapi.json")
        schema_response.raise_for_status()
        schema = schema_response.json()

        checked = 0
        skipped = 0
        failures: list[str] = []
        for path, methods in sorted((schema.get("paths") or {}).items()):
            operation = methods.get("get")
            if not operation:
                continue

            parameters = [
                *(methods.get("parameters") or []),
                *(operation.get("parameters") or []),
            ]
            requires_input = "{" in path or any(p.get("required") for p in parameters)
            if path in SKIP or requires_input:
                skipped += 1
                continue

            try:
                response = client.get(f"{BASE}{path}")
            except Exception as exc:
                failures.append(f"GET {path}: {exc}")
                continue

            checked += 1
            if 200 <= response.status_code < 300:
                print(f"OK  {response.status_code} GET {path}")
                continue
            body = (response.text or "")[:160]
            if (
                response.status_code == 503
                and path.startswith(OPTIONAL_DISABLED_PREFIXES)
                and "disabled" in body.lower()
            ):
                skipped += 1
                checked -= 1
                print(f"SKIP {response.status_code} GET {path} (optional feature off)")
                continue
            failures.append(f"GET {path}: HTTP {response.status_code} {body!r}")

    print(
        f"\nOpenAPI GET audit: checked={checked} skipped={skipped} "
        f"failed={len(failures)}"
    )
    for failure in failures:
        print(f"FAIL {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
