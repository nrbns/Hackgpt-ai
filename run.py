"""Start SecuraIQ server."""

import os

import uvicorn

from app.config import settings

if __name__ == "__main__":
    # Lab reload picks up API changes (e.g. /api/scans) without a manual restart.
    # Production / Docker should keep reload off.
    reload = (settings.deployment_mode or "lab").lower() in {"lab", "dev", "development"}
    if os.environ.get("UVICORN_RELOAD", "").strip().lower() in {"0", "false", "no"}:
        reload = False
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=reload,
    )
