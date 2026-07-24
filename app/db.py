"""SQLite persistence for users, engagements, chats, audit, memory, files."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from app.config import settings

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _db_path() -> Path:
    path = Path(settings.data_dir) / "securaiq.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_conn() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            _conn = sqlite3.connect(str(_db_path()), check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL;")
            _conn.execute("PRAGMA foreign_keys=ON;")
            init_schema(_conn)
        return _conn


def init_schema(conn: sqlite3.Connection | None = None) -> None:
    c = conn or get_conn()
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at REAL NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS api_keys (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            key_prefix TEXT NOT NULL,
            key_hash TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS engagements (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            scope_notes TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY,
            engagement_id TEXT REFERENCES engagements(id) ON DELETE SET NULL,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            mode TEXT NOT NULL DEFAULT 'default',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            action TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '{}',
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            engagement_id TEXT NOT NULL REFERENCES engagements(id) ON DELETE CASCADE,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            created_at REAL NOT NULL,
            UNIQUE(engagement_id, key)
        );
        CREATE TABLE IF NOT EXISTS files (
            id TEXT PRIMARY KEY,
            engagement_id TEXT REFERENCES engagements(id) ON DELETE SET NULL,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS gap_assessments (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            engagement_id TEXT,
            framework_id TEXT NOT NULL,
            title TEXT NOT NULL,
            evidence TEXT NOT NULL DEFAULT '',
            result_json TEXT NOT NULL,
            compliance_percent REAL NOT NULL DEFAULT 0,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS gap_remediations (
            id TEXT PRIMARY KEY,
            assessment_id TEXT NOT NULL REFERENCES gap_assessments(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL,
            engagement_id TEXT,
            control_id TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            owner TEXT NOT NULL DEFAULT '',
            due_date TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            recommendation TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS assets (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            engagement_id TEXT,
            name TEXT NOT NULL,
            asset_type TEXT NOT NULL DEFAULT 'server',
            criticality TEXT NOT NULL DEFAULT 'medium',
            owner TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS risks (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            engagement_id TEXT,
            asset_id TEXT,
            asset_name TEXT NOT NULL DEFAULT '',
            threat TEXT NOT NULL,
            vulnerability TEXT NOT NULL DEFAULT '',
            impact INTEGER NOT NULL DEFAULT 3,
            likelihood INTEGER NOT NULL DEFAULT 3,
            risk_score INTEGER NOT NULL DEFAULT 9,
            owner TEXT NOT NULL DEFAULT '',
            mitigation TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'open',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS vulnerabilities (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            engagement_id TEXT,
            asset_id TEXT,
            asset_name TEXT NOT NULL DEFAULT '',
            cve TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'medium',
            cvss REAL,
            status TEXT NOT NULL DEFAULT 'open',
            owner TEXT NOT NULL DEFAULT '',
            sla_due TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'import',
            raw_json TEXT NOT NULL DEFAULT '{}',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS playbooks (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            engagement_id TEXT,
            title TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'ir',
            severity TEXT NOT NULL DEFAULT 'high',
            steps TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'draft',
            owner TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS campaigns (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            engagement_id TEXT,
            name TEXT NOT NULL,
            campaign_type TEXT NOT NULL DEFAULT 'phishing_sim',
            audience TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'planned',
            sent_count INTEGER NOT NULL DEFAULT 0,
            click_count INTEGER NOT NULL DEFAULT 0,
            report_count INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS incidents (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            engagement_id TEXT,
            title TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'high',
            status TEXT NOT NULL DEFAULT 'open',
            source TEXT NOT NULL DEFAULT 'manual',
            owner TEXT NOT NULL DEFAULT '',
            playbook_id TEXT,
            summary TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS intel_watch (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT 'cve',
            value TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL
        );
        """
    )
    c.commit()


def new_id() -> str:
    return uuid.uuid4().hex


def now() -> float:
    return time.time()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def audit(action: str, user_id: str | None = None, detail: dict[str, Any] | None = None) -> None:
    c = get_conn()
    c.execute(
        "INSERT INTO audit_log (id, user_id, action, detail, created_at) VALUES (?, ?, ?, ?, ?)",
        (new_id(), user_id, action, json.dumps(detail or {}), now()),
    )
    c.commit()
