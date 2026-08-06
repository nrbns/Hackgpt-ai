#!/usr/bin/env bash
# Start SecuraIQ (Linux/macOS) — zero-config, no manual .env; --lan for Wi-Fi devices
set -euo pipefail
cd "$(dirname "$0")/.."

LAN=0
for arg in "$@"; do
  case "$arg" in
    --lan|-Lan) LAN=1 ;;
  esac
done

find_python() {
  if command -v python3 >/dev/null 2>&1; then
    echo python3
  elif command -v python >/dev/null 2>&1; then
    echo python
  else
    echo "Python 3 not found. Install python3 and retry." >&2
    exit 1
  fi
}

PY="$(find_python)"

if [ ! -d .venv ] || [ ! -x .venv/bin/python ]; then
  echo "Creating virtual environment..."
  "$PY" -m venv .venv
  echo "Installing dependencies (first run)..."
  .venv/bin/pip install --upgrade pip -q
  .venv/bin/pip install -r requirements.txt
fi

if [ ! -f .env.example ]; then
  echo "Missing .env.example - clone the full SecuraIQ repo." >&2
  exit 1
fi
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example (no manual editing needed)"
fi

set_env() {
  local key="$1" val="$2"
  if grep -q "^${key}=" .env 2>/dev/null; then
    sed -i.bak "s|^${key}=.*|${key}=${val}|" .env && rm -f .env.bak
  else
    echo "${key}=${val}" >> .env
  fi
}

if [ "$LAN" -eq 1 ]; then
  set_env HOST 0.0.0.0
else
  set_env HOST 127.0.0.1
  set_env CORS_ORIGINS "http://127.0.0.1:8080,http://localhost:8080"
fi
set_env AUTH_ALLOW_REGISTER false
set_env WORKSPACE_ZERO_START true
if command -v ollama >/dev/null 2>&1; then
  set_env MODEL_BACKEND ollama
fi

echo ""
if [ "$LAN" -eq 1 ]; then
  echo "Starting SecuraIQ (LAN mode)"
  echo "  This PC:     http://127.0.0.1:8080"
  if command -v hostname >/dev/null 2>&1; then
    (hostname -I 2>/dev/null || true) | tr ' ' '\n' | while read -r ip; do
      case "$ip" in
        ""|127.*|169.254.*) ;;
        *) echo "  Phone/other: http://${ip}:8080" ;;
      esac
    done
  fi
else
  echo "Starting SecuraIQ (localhost)"
  echo "  Open:  http://127.0.0.1:8080"
  echo "  LAN:   ./scripts/start.sh --lan"
fi
echo "No .env editing required. Optional keys: Settings in the UI."
.venv/bin/python run.py
