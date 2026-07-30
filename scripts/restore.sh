#!/usr/bin/env bash
# SecuraIQ restore — restores a backup produced by scripts/backup.sh.
# Usage: bash scripts/restore.sh backups/20260728T120000Z
set -euo pipefail
cd "$(dirname "$0")/.."

SRC="${1:?Usage: bash scripts/restore.sh <backup_dir>}"
DATA_DIR="${DATA_DIR:-data}"

if [ ! -d "$SRC" ]; then
  echo "Backup directory not found: $SRC" >&2
  exit 1
fi

echo "This will OVERWRITE the current $DATA_DIR/securaiq.db, chroma index, and uploads."
read -r -p "Type 'restore' to continue: " confirm
if [ "$confirm" != "restore" ]; then
  echo "Aborted."
  exit 1
fi

mkdir -p "$DATA_DIR"

if [ -f "$SRC/securaiq.db" ]; then
  cp "$SRC/securaiq.db" "$DATA_DIR/securaiq.db"
  echo "Restored SQLite DB."
fi

if [ -f "$SRC/chroma.tar.gz" ]; then
  rm -rf "$DATA_DIR/chroma"
  tar -xzf "$SRC/chroma.tar.gz" -C "$DATA_DIR"
  echo "Restored Chroma index."
fi

if [ -f "$SRC/uploads.tar.gz" ]; then
  rm -rf "$DATA_DIR/uploads"
  tar -xzf "$SRC/uploads.tar.gz" -C "$DATA_DIR"
  echo "Restored uploads."
fi

echo "Restore complete. Restart the app for changes to take effect."
