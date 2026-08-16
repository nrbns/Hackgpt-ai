#!/usr/bin/env bash
# Start SecuraIQ reachable by phones / other PCs on the same Wi‑Fi.
# Prints http://YOUR-LAN-IP:8080 — open that URL on the other device.
set -euo pipefail
cd "$(dirname "$0")"
exec bash scripts/start.sh --lan "$@"
