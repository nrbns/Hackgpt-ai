#!/usr/bin/env bash
# Start PentestGPT (Linux/macOS)
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/common.sh

ensure_venv
python -m pip install -r requirements.txt -q
ensure_env

echo "Starting PentestGPT at http://localhost:8080"
python run.py