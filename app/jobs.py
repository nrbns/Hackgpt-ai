"""Lightweight in-process background job runner.

"Background jobs / workers" was listed as not-started in
docs/launch-readiness.md. Rather than pull in Celery/Redis/APScheduler for a
single-process local-first alpha, this gives SecuraIQ:

  * a durable `jobs` table (survives restarts — a job left "pending" or
    "running" when the process died is requeued on next boot),
  * an asyncio worker loop (single worker is enough for alpha; bump
    WORKER_CONCURRENCY if a heavier job type shows up),
  * a periodic scheduler for recurring work (currently: CISA KEV cache
    refresh so it doesn't only refresh when a user happens to hit the intel
    endpoint).

Once the Redis compose profile / Postgres lands (see docs/postgres-migration.md),
this queue can move to an RQ/Celery worker without changing the handler
registry below — `JOB_HANDLERS` is the seam.
"""

from __future__ import annotations

import asyncio
import json
import time
import traceback
from typing import Any, Awaitable, Callable

from app.db import get_conn, new_id, now, row_to_dict

JobHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

JOB_HANDLERS: dict[str, JobHandler] = {}
_queue: "asyncio.Queue[str] | None" = None
_worker_task: asyncio.Task | None = None
_scheduler_task: asyncio.Task | None = None

KEV_SYNC_INTERVAL_SEC = 6 * 3600  # matches the 12h KEV cache TTL with margin
_SCHEDULER_TICK_SEC = 300  # poll granularity; each job kind tracks its own interval below
_last_kev_sync = 0.0
_last_xdr_sync = 0.0
_last_wazuh_sync = 0.0


def register_job(kind: str):
    """Decorator: @register_job("kev_sync") async def handler(payload) -> dict"""

    def _wrap(fn: JobHandler) -> JobHandler:
        JOB_HANDLERS[kind] = fn
        return fn

    return _wrap


def enqueue_job(
    kind: str,
    payload: dict[str, Any] | None = None,
    *,
    engine: str = "auto",
) -> dict[str, Any]:
    if kind not in JOB_HANDLERS:
        raise ValueError(f"Unknown job kind '{kind}'. Registered: {sorted(JOB_HANDLERS)}")
    body = dict(payload or {})
    eng = (engine or "auto").lower().strip()
    if eng == "auto":
        try:
            from app.prefect_bridge import prefect_status

            eng = "prefect" if prefect_status().get("ready") else "local"
        except Exception:
            eng = "local"
    if eng not in ("local", "prefect"):
        raise ValueError("engine must be local, prefect, or auto")
    body["_engine"] = eng
    jid = new_id()
    c = get_conn()
    c.execute(
        "INSERT INTO jobs (id, kind, status, payload_json, result_json, error, created_at) "
        "VALUES (?, ?, 'pending', ?, '{}', '', ?)",
        (jid, kind, json.dumps(body), now()),
    )
    c.commit()
    if _queue is not None:
        _queue.put_nowait(jid)
    return get_job(jid)  # type: ignore[return-value]


def get_job(job_id: str) -> dict[str, Any] | None:
    row = get_conn().execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    d = row_to_dict(row)
    if d:
        for key in ("payload_json", "result_json"):
            try:
                d[key.replace("_json", "")] = json.loads(d.get(key) or "{}")
            except Exception:
                pass
    return d


def list_jobs(limit: int = 50, kind: str | None = None) -> list[dict[str, Any]]:
    c = get_conn()
    q = "SELECT * FROM jobs"
    args: list[Any] = []
    if kind:
        q += " WHERE kind = ?"
        args.append(kind)
    q += " ORDER BY created_at DESC LIMIT ?"
    args.append(max(1, min(limit, 200)))
    out = []
    for row in c.execute(q, args).fetchall():
        d = dict(row)
        for key in ("payload_json", "result_json"):
            try:
                d[key.replace("_json", "")] = json.loads(d.get(key) or "{}")
            except Exception:
                pass
        out.append(d)
    return out


def _has_pending_or_running(kind: str) -> bool:
    row = get_conn().execute(
        "SELECT COUNT(*) AS n FROM jobs WHERE kind = ? AND status IN ('pending', 'running')",
        (kind,),
    ).fetchone()
    return bool(row and int(row["n"]) > 0)


async def _run_one(job_id: str) -> None:
    job = get_job(job_id)
    if not job or job.get("status") not in ("pending",):
        return
    c = get_conn()
    c.execute("UPDATE jobs SET status='running', started_at=? WHERE id=?", (now(), job_id))
    c.commit()
    handler = JOB_HANDLERS.get(job["kind"])
    try:
        if not handler:
            raise ValueError(f"No handler registered for kind '{job['kind']}'")
        payload = json.loads(job.get("payload_json") or "{}")
        engine = (payload.pop("_engine", None) or "local").lower()
        if engine == "prefect":
            from app.prefect_bridge import run_kind_via_prefect

            result = await run_kind_via_prefect(job["kind"], payload)
        else:
            result = await handler(payload)
            if isinstance(result, dict):
                result = {**result, "engine": "local"}
        c.execute(
            "UPDATE jobs SET status='done', result_json=?, finished_at=? WHERE id=?",
            (json.dumps(result or {}), now(), job_id),
        )
        c.commit()
    except Exception as exc:  # noqa: BLE001 — job errors must never crash the worker
        c.execute(
            "UPDATE jobs SET status='error', error=?, finished_at=? WHERE id=?",
            (f"{exc}\n{traceback.format_exc()[-2000:]}", now(), job_id),
        )
        c.commit()


async def _worker_loop() -> None:
    assert _queue is not None
    while True:
        job_id = await _queue.get()
        try:
            await _run_one(job_id)
        finally:
            _queue.task_done()


async def _scheduler_loop() -> None:
    # Stagger first run slightly so it doesn't compete with app startup.
    await asyncio.sleep(15)
    global _last_kev_sync, _last_xdr_sync, _last_wazuh_sync
    while True:
        now_t = time.time()
        try:
            if (
                "kev_sync" in JOB_HANDLERS
                and now_t - _last_kev_sync >= KEV_SYNC_INTERVAL_SEC
                and not _has_pending_or_running("kev_sync")
            ):
                _last_kev_sync = now_t
                enqueue_job("kev_sync", {"scheduled": True})
        except Exception:
            pass
        try:
            from app.config import settings

            interval = max(300, int(settings.xdr_sync_interval_sec))
            if (
                "xdr_sync" in JOB_HANDLERS
                and now_t - _last_xdr_sync >= interval
                and not _has_pending_or_running("xdr_sync")
            ):
                _last_xdr_sync = now_t
                enqueue_job("xdr_sync", {"scheduled": True})
        except Exception:
            pass
        try:
            from app.config import settings

            from app.connectors import wazuh as wazuh_conn

            w_interval = max(300, int(getattr(settings, "wazuh_sync_interval_sec", 1800) or 1800))
            if (
                "wazuh_sync" in JOB_HANDLERS
                and wazuh_conn.is_configured()
                and now_t - _last_wazuh_sync >= w_interval
                and not _has_pending_or_running("wazuh_sync")
            ):
                _last_wazuh_sync = now_t
                enqueue_job("wazuh_sync", {"scheduled": True})
        except Exception:
            pass
        await asyncio.sleep(_SCHEDULER_TICK_SEC)


def start_background_jobs() -> None:
    """Call once from the FastAPI lifespan startup."""
    global _queue, _worker_task, _scheduler_task
    if _queue is not None:
        return  # already started (e.g. lifespan re-entered under --reload)
    _queue = asyncio.Queue()

    # Requeue anything left pending/running from a previous process that died mid-job.
    c = get_conn()
    c.execute("UPDATE jobs SET status='pending', started_at=NULL WHERE status='running'")
    c.commit()
    for row in c.execute(
        "SELECT id FROM jobs WHERE status='pending' ORDER BY created_at ASC LIMIT 100"
    ).fetchall():
        _queue.put_nowait(row["id"])

    _worker_task = asyncio.create_task(_worker_loop())
    _scheduler_task = asyncio.create_task(_scheduler_loop())


async def stop_background_jobs() -> None:
    global _worker_task, _scheduler_task
    for task in (_worker_task, _scheduler_task):
        if task:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
    _worker_task = None
    _scheduler_task = None


# --- Built-in job handlers ---------------------------------------------------


@register_job("kev_sync")
async def _job_kev_sync(payload: dict[str, Any]) -> dict[str, Any]:
    from app.intel_feeds import fetch_cisa_kev

    t0 = time.time()
    feed = await fetch_cisa_kev(limit=payload.get("limit", 50))
    return {"count": feed.get("count"), "cached": feed.get("cached"), "duration_sec": round(time.time() - t0, 2)}


@register_job("xdr_sync")
async def _job_xdr_sync(payload: dict[str, Any]) -> dict[str, Any]:
    """Poll all configured XDR/EDR vendors and ingest new detections/patch gaps."""
    from app.xdr import sync_all

    t0 = time.time()
    result = await sync_all(payload.get("user_id", "local"))
    result["duration_sec"] = round(time.time() - t0, 2)
    return result


@register_job("wazuh_sync")
async def _job_wazuh_sync(payload: dict[str, Any]) -> dict[str, Any]:
    """Pull Wazuh agents + alerts into SecuraIQ (authorized manager/indexer)."""
    from app.wazuh import sync as wazuh_sync

    t0 = time.time()
    result = await wazuh_sync(payload.get("user_id", "local"))
    result["duration_sec"] = round(time.time() - t0, 2)
    return result


@register_job("report_export")
async def _job_report_export(payload: dict[str, Any]) -> dict[str, Any]:
    """Offload a heavy executive PDF build off the request thread."""
    from pathlib import Path

    from app.commercial_ext import build_executive_pdf

    user_id = payload.get("user_id", "local")
    pdf_bytes = await asyncio.to_thread(build_executive_pdf, user_id)
    out_dir = Path(payload.get("data_dir", "data")) / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"executive-{new_id()}.pdf"
    out_path.write_bytes(pdf_bytes)

    if user_id and user_id != "local":
        from app.notifications import notify

        notify(
            user_id,
            "system",
            "Executive report ready",
            f"Your executive PDF report finished generating ({len(pdf_bytes)} bytes).",
            link=str(out_path),
        )

    return {"path": str(out_path), "bytes": len(pdf_bytes)}
