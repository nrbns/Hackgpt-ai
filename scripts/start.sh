#!/usr/bin/env bash
# Start SecuraIQ (Linux/macOS)
cd "$(dirname "$0")/.."
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi
if [ ! -f .env ]; then
  cp .env.example .env
fi
echo "Starting SecuraIQ at http://localhost:8080"
.venv/bin/python run.py
