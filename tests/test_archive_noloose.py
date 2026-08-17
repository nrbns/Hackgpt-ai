"""Prototype no-loss archive: clear moves evidence under data/archive."""

from __future__ import annotations

import importlib
from pathlib import Path


def test_clear_archives_before_wipe(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("WORKSPACE_ZERO_START", "false")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("DATABASE_URL", "")

    import app.config as config_mod
    import app.db as db_mod

    importlib.reload(config_mod)
    db_mod.reset_conn_for_tests()
    importlib.reload(db_mod)

    from app.archive import find_archived_scan, list_archives, prototype_status
    from app.scan_engine.models import clear_user_scan_data, create_scan, ensure_scans_schema

    ensure_scans_schema()
    scan = create_scan(
        user_id="local",
        target="192.168.56.101",
        scanner="securaiq",
        profile="discovery",
        authorized=True,
    )
    ev = Path(scan["evidence_dir"])
    ev.mkdir(parents=True, exist_ok=True)
    (ev / "report.md").write_text("# archived prototype report\n", encoding="utf-8")

    proto = prototype_status()
    assert proto["data_persists"] is True

    result = clear_user_scan_data("local", archive=True)
    assert result["scans_deleted"] == 1
    assert result["archived_count"] >= 1
    assert find_archived_scan(scan["id"]) is not None
    assert any(a.get("scan_id") == scan["id"] for a in list_archives("local"))
    assert not ev.exists()
