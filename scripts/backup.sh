#!/usr/bin/env bash
# SecuraIQ backup — online SQLite backup (safe under WAL) + chroma index + evidence files.
# Usage: bash scripts/backup.sh [backup_dir]
set -euo pipefail
cd "$(dirname "$0")/.."

DATA_DIR="${DATA_DIR:-data}"
BACKUP_ROOT="${1:-backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="$BACKUP_ROOT/$STAMP"
mkdir -p "$OUT_DIR"

DB_PATH="$DATA_DIR/securaiq.db"
if [ -f "$DB_PATH" ]; then
  echo "Backing up SQLite DB (online .backup, safe with WAL)..."
  sqlite3 "$DB_PATH" ".backup '$OUT_DIR/securaiq.db'"
else
  echo "WARNING: $DB_PATH not found — skipping DB backup."
fi

if [ -d "$DATA_DIR/chroma" ]; then
  echo "Archiving Chroma vector index..."
  tar -czf "$OUT_DIR/chroma.tar.gz" -C "$DATA_DIR" chroma
fi

if [ -d "$DATA_DIR/uploads" ]; then
  echo "Archiving uploaded evidence/files..."
  tar -czf "$OUT_DIR/uploads.tar.gz" -C "$DATA_DIR" uploads
fi

if [ -f ".env" ]; then
  echo "NOTE: .env (contains secrets) is intentionally NOT included in the backup archive."
  echo "      Back it up separately via your secrets manager, not alongside app data."
fi

echo "Backup complete: $OUT_DIR"
echo "Retention is your responsibility — see docs/backup-dr.md for a suggested policy."
