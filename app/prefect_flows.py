"""Prefect flows wrapping SecuraIQ JOB_HANDLERS.

CLI::

    python -m app.prefect_flows                 # status JSON
    python -m app.prefect_flows --run kev_sync '{}'
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any


def _run_handler(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    # Import handlers (registers JOB_HANDLERS including scan_execute)
    import app.jobs  # noqa: F401
    import app.scan_engine.jobs  # noqa: F401
    from app.jobs import JOB_HANDLERS

    handler = JOB_HANDLERS.get(kind)
    if not handler:
        raise ValueError(f"Unknown job kind '{kind}'. Registered: {sorted(JOB_HANDLERS)}")
    return asyncio.run(handler(payload or {}))


try:
    from prefect import flow, task
except ImportError:  # pragma: no cover - optional dependency

    def securaiq_job_flow(kind: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        raise RuntimeError("Prefect is not installed. pip install 'prefect>=3.0,<4'")

else:

    @task(name="securaiq-job-handler", retries=1, retry_delay_seconds=5)
    def securaiq_job_task(kind: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return _run_handler(kind, payload or {})

    @flow(name="securaiq-job", log_prints=True)
    def securaiq_job_flow(kind: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Golden-path unit: one SecuraIQ background job under Prefect."""
        result = securaiq_job_task(kind, payload or {})
        if isinstance(result, dict):
            return {**result, "engine": "prefect", "kind": kind}
        return {"result": result, "engine": "prefect", "kind": kind}


def main() -> None:
    from app.prefect_bridge import prefect_status

    args = sys.argv[1:]
    if args and args[0] == "--run":
        if len(args) < 2:
            print("usage: python -m app.prefect_flows --run <kind> [payload_json]", file=sys.stderr)
            sys.exit(2)
        kind = args[1]
        payload = json.loads(args[2]) if len(args) > 2 else {}
        result = securaiq_job_flow(kind, payload)
        # Stable machine-readable line for the parent API process
        print("RESULT_JSON:" + json.dumps(result, ensure_ascii=False, default=str))
        return

    print(json.dumps(prefect_status(), indent=2))


if __name__ == "__main__":
    main()
