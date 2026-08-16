"""Run DB migrations then start SecuraIQ (SaaS / production entrypoint)."""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> None:
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if url.startswith("postgres://") or url.startswith("postgresql://"):
        print("Running Alembic migrations…", flush=True)
        rc = subprocess.call([sys.executable, "-m", "alembic", "upgrade", "head"])
        if rc != 0:
            print("Alembic failed — refusing to start", flush=True)
            sys.exit(rc)
    else:
        print("No Postgres DATABASE_URL — skipping Alembic (SQLite/lab mode)", flush=True)
    os.execv(sys.executable, [sys.executable, "run.py"])


if __name__ == "__main__":
    main()
