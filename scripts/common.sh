#!/usr/bin/env bash
# Shared shell helpers for Linux/macOS scripts.
set -euo pipefail

project_root() {
  cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
}

python_cmd() {
  if command -v python3 >/dev/null 2>&1; then
    echo python3
  elif command -v python >/dev/null 2>&1; then
    echo python
  else
    echo "Python 3 is required." >&2
    exit 1
  fi
}

ensure_venv() {
  local py
  py="$(python_cmd)"
  if [ ! -d ".venv" ]; then
    "$py" -m venv .venv
  fi
  # shellcheck disable=SC1091
  . .venv/bin/activate
}

ensure_env() {
  if [ ! -f ".env" ]; then
    cp .env.example .env
  fi
}

set_env_value() {
  local key="$1"
  local value="$2"
  ensure_env
  awk -v key="$key" -v value="$value" '
    BEGIN { found = 0 }
    $0 ~ "^" key "=" { print key "=" value; found = 1; next }
    { print }
    END { if (!found) print key "=" value }
  ' .env > .env.tmp
  mv .env.tmp .env
}

stop_port_8080() {
  if command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -ti tcp:8080 || true)"
    if [ -n "${pids:-}" ]; then
      kill $pids 2>/dev/null || true
    fi
  elif command -v fuser >/dev/null 2>&1; then
    fuser -k 8080/tcp 2>/dev/null || true
  fi
}