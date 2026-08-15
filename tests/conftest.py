"""Shared pytest fixtures.

Keeps the test suite import-light on purpose: most modules under test
(scanner_adapters, realtime_bus, integrations_catalog) have zero app-internal
imports, so they're safe to unit-test without a DB, a running event loop, or
network access. Anything that touches app.db gets an isolated temp SQLite
file via the `tmp_data_dir` fixture below — never the real data/ directory.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture()
def tmp_data_dir(tmp_path, monkeypatch):
    """Point DATA_DIR at a throwaway directory for the duration of one test.

    Must be set *before* app.config/app.db are imported for the first time in
    a given process, since Settings() and get_conn() cache paths at import
    time — tests that need this should import the relevant app module inside
    the test function, after the fixture has set the env var, not at module
    scope.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("WORKSPACE_ZERO_START", "false")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    yield data_dir
