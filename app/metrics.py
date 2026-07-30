"""Minimal operational metrics — Prometheus text exposition, no new dependency.

"Monitoring / error reporting" was listed as **Todo** in
docs/commercial-roadmap.md's SaaS readiness checklist. This is the
self-hosted-friendly half of that: an in-memory counter set exposed at
`GET /api/metrics` in the standard Prometheus text format, scrapeable by
Prometheus/Grafana/Datadog/whatever the operator already runs — no vendor
lock-in, no external service required.

Error *reporting* (crash aggregation, stack traces, alerting) is a separate
concern better served by an actual APM — see `app/error_reporting.py` for
the optional Sentry hook, which is additive and inert without SENTRY_DSN.
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

_start_time = time.time()
_lock = Lock()
_counters: dict[str, int] = defaultdict(int)
_status_counters: dict[str, int] = defaultdict(int)


def incr(name: str, amount: int = 1) -> None:
    with _lock:
        _counters[name] += amount


def incr_status(status_code: int) -> None:
    bucket = f"{status_code // 100}xx"
    with _lock:
        _status_counters[bucket] += 1


def render_prometheus() -> str:
    from app.jobs import list_jobs

    lines: list[str] = []

    lines.append("# HELP securaiq_uptime_seconds Process uptime in seconds.")
    lines.append("# TYPE securaiq_uptime_seconds gauge")
    lines.append(f"securaiq_uptime_seconds {time.time() - _start_time:.2f}")

    with _lock:
        counters_snapshot = dict(_counters)
        status_snapshot = dict(_status_counters)

    lines.append("# HELP securaiq_http_requests_total Total HTTP requests handled.")
    lines.append("# TYPE securaiq_http_requests_total counter")
    for name, value in sorted(counters_snapshot.items()):
        safe_name = name.replace("-", "_").replace(".", "_")
        lines.append(f'securaiq_http_requests_total{{route="{safe_name}"}} {value}')

    lines.append("# HELP securaiq_http_responses_total Total HTTP responses by status class.")
    lines.append("# TYPE securaiq_http_responses_total counter")
    for bucket, value in sorted(status_snapshot.items()):
        lines.append(f'securaiq_http_responses_total{{class="{bucket}"}} {value}')

    try:
        jobs = list_jobs(limit=500)
        by_status: dict[str, int] = defaultdict(int)
        for j in jobs:
            by_status[j.get("status", "unknown")] += 1
        lines.append("# HELP securaiq_jobs_total Background jobs by status (last 500).")
        lines.append("# TYPE securaiq_jobs_total gauge")
        for status, count in sorted(by_status.items()):
            lines.append(f'securaiq_jobs_total{{status="{status}"}} {count}')
    except Exception:
        pass

    return "\n".join(lines) + "\n"
